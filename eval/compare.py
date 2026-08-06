import os
import sys
import pandas as pd
import argparse
import json
from evaluate import LoMAEvaluation
# sys.path.append("/app")

from tqdm import tqdm
from ollama import Client
from pydantic import BaseModel, Field

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Models Comparison")
    parser.add_argument("--base", type=str, required=True, help="Excel file with base model responses.")
    parser.add_argument("--finetuned", type=str, required=True, help="Excel file with fine-tuned model responses.")
    parser.add_argument("--quantized", type=str, required=True, help="Excel file with quantized fine-tuned model responses.")
    parser.add_argument("--column", type=str, required=True, help="Column containing questions for evaluation.")

    args = parser.parse_args()

    evaluator = LoMAEvaluation()

    for eval_model in evaluator.get_judges():
        evaluator.compare_responses(
            args=args,
            eval_model=eval_model,
            basemodel_path=os.path.join("/app", "eval", args.base + ".xlsx"),
            finetuned_path=os.path.join("/app", "eval", args.finetuned + ".xlsx"),
            quantized_path=os.path.join("/app", "eval", args.quantized + ".xlsx"),
            compare_path=os.path.join("/app", "eval", "comp_responses_{eval_model}.xlsx")
        )