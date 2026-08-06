import os
import sys
import pandas as pd
import argparse
import json

from prompts import (
    EVAL_SYS_PROMPT, 
    EVAL_USR_PROMPT,
    COMPARE_SYS_PROMPT,
    COMPARE_USR_PROMPT
)
sys.path.append("/app")

from agents import Agents
from tqdm import tqdm
from ollama import Client
from pydantic import BaseModel, Field
from typing import Literal

class ResponseEvaluation(BaseModel):
    reasoning: str = Field(description="Step-by-step linguistic analysis")
    l1_score: int = Field(description="Domain terminology score (1–5)")
    l2_score: int = Field(description="Professional register score (1–5)")
    l3_score: int = Field(description="Expressive coherence score (1–5)")

class CompareEvaluation(BaseModel):
    reasoning: str = Field(description="Step-by-step comparative linguistic analysis of all three responses")
    preference_reasoning: str = Field(description="Brief justification for the preferred output choice")
    preferred_output: Literal[1, 2, 3, 0] = Field(
        description="1=Output1 (baseline), 2=Output2 (fine-tuned), 3=Output3 (quantized), 0=no_preference"
    )

class LoMAEvaluation:
    def __init__(self, host: str = "http://ollama:11434", limit_retries: int = 5):
        agents = Agents()
        self.team = agents.get_team_agent()
        self.team = None
        self.oclient = Client(host=host)
        self.limit_retries = limit_retries

    def _unload_model(self, model):
        self.oclient.chat(model=model, messages=[{"role": "user", "content": ""}], keep_alive=0)

    @staticmethod
    def get_judges():
        return [
            "gpt-oss:20b",
            "mistral-small3.2",
            "nemotron3:33b",
            "qwen2.5:32b",
            "llama3.3:latest"
        ]

    def generate(self, args, excel_path, output_path):
        df = pd.read_excel(excel_path)

        for i, row in tqdm(df.iterrows(), total=len(df), desc="Generating Responses - LoMA Agent"):
            count_retries = 0
            completed = False
            while not completed:
                try:
                    response = self.team.run(row[args.column])
                    df.at[i, 'agent_response'] = response.content
                    print("\nQUESTION: ", row[args.column])
                    print("AGENT ANSWER: ", response.content)
                    completed = True
                except Exception as e:
                    if count_retries < self.limit_retries:
                        print(f"ERROR QUESTION '{row[args.column]}': {str(e)}, retry.")
                        count_retries += 1
                        continue
                    df.at[i, 'error'] = str(e)
        df.to_excel(output_path)

        return df

    def evaluate(self, df, args, eval_model, eval_path):
        for i, row in tqdm(df.iterrows(), total=len(df), desc="Evaluating Responses - LoMA Agent"):
            if (i + 1) % 10 == 0:
                self._unload_model(model=eval_model)
            
            prompt = EVAL_USR_PROMPT.format(
                question=row[args.column],
                answer=row['answer'],
                agent_response=row['agent_response']
            )

            attempt = 0
            success = False

            while attempt < self.limit_retries and not success:
                try:
                    response = self.oclient.chat(
                        model=eval_model,
                        messages=[
                            {"role": "system", "content": EVAL_SYS_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        format=ResponseEvaluation.model_json_schema(),
                        options={
                            "num_ctx": 32768,
                            "temperature": 0.1
                        }
                    )

                    content = response.get("message", {}).get("content", "")

                    if not content:
                        self._unload_model(model=eval_model)
                        attempt += 1
                        continue

                    data = ResponseEvaluation(**json.loads(content))
                    df.at[i, 'judge_reasoning'] = data.reasoning
                    df.at[i, 'l1_score'] = data.l1_score
                    df.at[i, 'l2_score'] = data.l2_score
                    df.at[i, 'l3_score'] = data.l3_score
                    success = True
                except Exception as e:
                    attempt += 1
                    print(f"\n[ERROR] Row {i} (Attempt {attempt}/{self.limit_retries}): {e}")
                    if attempt >= self.limit_retries:
                        df.at[i, 'judge_reasoning'] = f"Evaluation failed after {self.limit_retries} attempts: {str(e)}"
                        df.at[i, 'l1_score'] = None
                        df.at[i, 'l2_score'] = None
                        df.at[i, 'l3_score'] = None

        df.to_excel(eval_path)

        return df
    
    def compare_responses(self, args, eval_model, basemodel_path, finetuned_path, quantized_path, compare_path):
        df_base = pd.read_excel(basemodel_path)
        df_finetuned = pd.read_excel(finetuned_path)
        df_quantized = pd.read_excel(quantized_path)

        rows = []
        for (i, row_base), (_, row_ft), (_, row_qt) in tqdm(zip(df_base.iterrows(), df_finetuned.iterrows(), df_quantized.iterrows()), total=len(df_base), desc="Comparing Responses"):
            if (i + 1) % 10 == 0:
                self._unload_model(model=eval_model)

            prompt = COMPARE_USR_PROMPT.format(
                question=row_base[args.column],
                answer=row_base['answer'],
                m1_response=row_base['agent_response'],
                m2_response=row_ft['agent_response'],
                m3_response=row_qt['agent_response']
            )

            attempt = 0
            success = False

            while attempt < self.limit_retries and not success:
                try:
                    response = self.oclient.chat(
                        model=eval_model,
                        messages=[
                            {"role": "system", "content": COMPARE_SYS_PROMPT},
                            {"role": "user", "content": prompt}
                        ],
                        format=CompareEvaluation.model_json_schema(),
                        options={
                            "num_ctx": 32768,
                            "temperature": 0.1
                        }
                    )

                    content = response.get("message", {}).get("content", "")
                    if not content:
                        self._unload_model(model=eval_model)
                        attempt += 1
                        continue

                    data = CompareEvaluation(**json.loads(content))
                    rows.append({
                        "language": row_base["language"],
                        "category_label": row_base["category_label"],
                        "question": row_base[args.column],
                        "base_response": row_base["agent_response"],
                        "ft_response": row_ft["agent_response"],
                        "qt_response": row_qt["agent_response"],
                        "preferred_output": data.preferred_output,
                        "preference_reasoning": data.preference_reasoning,
                        "reasoning": data.reasoning
                    })
                    success = True
                except Exception as e:
                    attempt += 1
                    print(f"\n[ERROR] Row {i} (Attempt {attempt}/{self.limit_retries}): {e}")
                    if attempt >= self.limit_retries:
                        rows.append({
                            "question": row_base[args.column],
                            "base_response": row_base['agent_response'],
                            "ft_response": row_ft['agent_response'],
                            "qt_response": row_qt['agent_response'],
                            "preferred_output": None,
                            "preference_reasoning": None,
                            "reasoning": f"Failed after {self.limit_retries} attempts: {e}",
                        })

        df_compare = pd.DataFrame(rows)
        df_compare.to_excel(compare_path, index=False)
        return df_compare

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluation")
    parser.add_argument("--file", type=str, required=True, help="Excel file with questions to evaluate (omit extension).")
    parser.add_argument("--column", type=str, required=True, help="Column containing questions for evaluation.")
    parser.add_argument("--output", type=str, required=True, help="Output file name (omit extension, the file will be <output>.xlsx).")

    args = parser.parse_args()

    evaluator = LoMAEvaluation()

    # Answer generation
    df = evaluator.generate(
        args=args, 
        excel_path=os.path.join("/app", "eval", args.file + ".xlsx"),
        output_path=os.path.join("/app", "eval", args.output + ".xlsx")
    )

    # Evaluation
    excel_path = os.path.join("/app", "eval", args.output + ".xlsx")

    for eval_model in evaluator.get_judges():
        df = pd.read_excel(excel_path)
        print(f"--- EVALUTATING WITH {eval_model} ---")
        eval_path = os.path.join("/app", "eval", args.output + f"_eval_{eval_model}.xlsx")
        evaluator.evaluate(
            df=df,
            eval_model=eval_model,
            args=args,
            eval_path=os.path.join("/app", "eval", args.output + f"_eval_{eval_model}.xlsx")
        )