import os
import argparse
import json
import pandas as pd
import numpy as np
import krippendorff
import pingouin as pg
from scipy.stats import friedmanchisquare, wilcoxon
from typing import List, Dict, Optional, Tuple
from evaluate import LoMAEvaluation
from collections import defaultdict

class LoMAMetrics:
    def __init__(
        self,
        eval_paths: Dict[str, Dict[str, str]],
        comp_paths: Dict[str, str],
        judges: List[str],
        dimensions: List[str] = None,
    ):
        self.alpha = 0.05
        self.bonferroni_alpha = self.alpha / 3
 
        self.models = list(next(iter(eval_paths.values())).keys())
        self.model_labels = {"no_tuning": "M1", "q8_0": "M2", "q4_k_m": "M3"}
        self.dimensions = dimensions or ["l1_score", "l2_score", "l3_score"]
 
        self.judges = judges
 
        self.df_eval = defaultdict(dict)
        for judge, evals in eval_paths.items():
            for model, path in evals.items():
                self.df_eval[judge][model] = (
                    pd.read_excel(path)
                    .dropna(subset=self.dimensions)
                    .set_index("question")
                )
 
        self.df_comp = {}
        for judge, path in comp_paths.items():
            self.df_comp[judge] = pd.read_excel(path)

    @staticmethod
    def _get_bonferroni_pairs():
        return [
            ("no_tuning", "q8_0"),
            ("no_tuning", "q4_k_m"),
            ("q8_0", "q4_k_m"),
        ]
 
    def _scores_for(self, judge: str, model: str, dim: str, language: Optional[str] = None):
        """
        Return a 1-D array of scores for a given judge / model / dimension,
        optionally filtered by language.
        """
        df = self.df_eval[judge][model]
        if language is not None and "language" in df.columns:
            df = df[df["language"] == language]
        return df[dim].to_numpy(dtype=float)

    def _get_questions(self, judge: str, lang: str) -> list:
        sets = []
        for model in self.models:
            df = self.df_eval[judge][model]
            if lang != "all" and "language" in df.columns:
                df = df[df["language"] == lang]
            sets.append(set(df.index.tolist()))
        return list(set.intersection(*sets))
 
    def _collect_paired_scores(self, lang: str, dim: str) -> Dict[str, list]:
        scores_per_model = defaultdict(list)
 
        for judge in self.judges:
            questions = self._get_questions(judge, lang)
            if not questions:
                continue
 
            for model in self.models:
                df = self.df_eval[judge][model]
                if lang != "all" and "language" in df.columns:
                    df = df[df["language"] == lang]
                scores_per_model[model].extend(
                    df.loc[questions, dim].tolist()
                )
 
        return {model: np.array(scores, dtype=float) for model, scores in scores_per_model.items()}
 
    def _get_all_languages(self) -> list:
        """Return unique languages across all judges and models."""
        langs = set()
        for judge in self.judges:
            ref_df = next(iter(self.df_eval[judge].values()))
            if "language" in ref_df.columns:
                langs.update(ref_df["language"].unique().tolist())
        return list(langs) if langs else ["all"]

    def _mos(self):
        """ Average Liket score per dimension, per model, per language. """
        results = defaultdict(lambda: defaultdict(dict))

        for model in self.models:
            lang_dim_scores = defaultdict(lambda: defaultdict(list))
 
            for judge in self.judges:
                df = self.df_eval[judge][model]
                languages = df["language"].unique() if "language" in df.columns else ["all"]
                for lang in languages:
                    sub = df[df["language"] == lang] if "language" in df.columns else df
                    for dim in self.dimensions:
                        lang_dim_scores[lang][dim].extend(sub[dim].dropna().tolist())
 
            for lang, dim_scores in lang_dim_scores.items():
                for dim, scores in dim_scores.items():
                    scores = np.array(scores, dtype=float)
                    n = len(scores)
                    mean = scores.mean()
                    std = scores.std(ddof=1) if n > 1 else 0.0
                    ci_half = 1.96 * (std / np.sqrt(n)) if n > 0 else 0.0
                    results[lang][model][dim] = {
                        "mean": round(mean, 3),
                        "std": round(std, 3),
                        "ci95_low": round(mean - ci_half, 3),
                        "ci95_high": round(mean + ci_half, 3),
                        "n": n,
                    }
 
        return dict(results)

    def _friedman(self):
        """ States if the 3 models differ. """
        results = defaultdict(dict)
        languages = self._get_all_languages()

        for lang in languages:
            for dim in self.dimensions:
                paired_scores = self._collect_paired_scores(lang, dim)
                scores = [paired_scores[model] for model in self.models]

                n = min(len(score) for score in scores)

                if n < 3:
                    results[lang][dim] = {
                        "stat": None,
                        "p": None,
                        "significant": None,
                        "note": "insufficient data",
                        "n_blocks": n
                    }
                    continue

                stat, p = friedmanchisquare(*scores)
                results[lang][dim] = {
                    "stat": round(float(stat), 4),
                    "p": round(float(p), 4),
                    "significant": bool(p < self.alpha),
                    "n_blocks": n
                }
        
        return dict(results)

    def _wilcoxon_bonferroni(self):
        """ Pairwise post-hoc, which pairs differ. """
        results = defaultdict(lambda: defaultdict(dict))
        pairs = self._get_bonferroni_pairs()
        languages = self._get_all_languages()

        for lang in languages:
            for dim in self.dimensions:
                paired = self._collect_paired_scores(lang, dim)

                for m_a, m_b in pairs:
                    pair_label = f"{m_a}_vs_{m_b}"
                    scores_a = paired[m_a]
                    scores_b = paired[m_b]
                    n = min(len(scores_a), len(scores_b))
                    scores_a, scores_b = scores_a[:n], scores_b[:n]

                    if n < 2 or np.array_equal(scores_a, scores_b):
                        results[lang][dim][pair_label] = {
                            "stat": None, 
                            "p": None, 
                            "p_bonf": None,
                            "significant": None,
                            "note": "identical or insufficient data",
                        }
                        continue
                        
                    try:
                        stat, p = wilcoxon(scores_a, scores_b)
                        results[lang][dim][pair_label] = {
                            "stat": round(float(stat), 4),
                            "p": round(float(p), 4),
                            "p_bonf": round(float(min(p * 3, 1.0)), 4),
                            "significant": bool(p < self.bonferroni_alpha),
                            "n_blocks": n,
                        }
                    except Exception as e:
                        results[lang][dim][pair_label] = {
                            "stat": None, 
                            "p": None, 
                            "p_bonf": None,
                            "significant": None, 
                            "note": str(e),
                        }
        
        return dict(results)

    def _cohen_r(self):
        """ Magnitude of each pairwise difference. """
        def _interpret(r_abs: float) -> str:
            if r_abs > 0.50: return "large"
            elif r_abs > 0.30: return "medium"
            elif r_abs > 0.10: return "small"
            return "negligible"
 
        results = defaultdict(lambda: defaultdict(dict))
        pairs = self._get_bonferroni_pairs()
        languages = self._get_all_languages()
 
        for lang in languages:
            for dim in self.dimensions:
                paired = self._collect_paired_scores(lang, dim)
 
                for m_a, m_b in pairs:
                    pair_label = f"{m_a}_vs_{m_b}"
                    scores_a = paired[m_a]
                    scores_b = paired[m_b]
                    n = min(len(scores_a), len(scores_b))
                    scores_a, scores_b = scores_a[:n], scores_b[:n]
 
                    if n < 2 or np.array_equal(scores_a, scores_b):
                        results[lang][dim][pair_label] = {
                            "r": None, "interpretation": None,
                            "note": "identical or insufficient data",
                        }
                        continue
 
                    try:
                        result = pg.wilcoxon(scores_a, scores_b)
                        r = float(result["RBC"].values[0])
                        results[lang][dim][pair_label] = {
                            "r": round(r, 4),
                            "interpretation": _interpret(abs(r)),
                            "n_blocks": n,
                        }
                    except Exception as e:
                        results[lang][dim][pair_label] = {
                            "r": None, "interpretation": None, "note": str(e),
                        }
 
        return dict(results)

    def _krippendorff(self):
        """ Inter-rater reliability across evaluators. """
        results = defaultdict(lambda: defaultdict(dict))
 
        for model in self.models:
            ref_df = self.df_eval[self.judges[0]][model]
            languages = ref_df["language"].unique() if "language" in ref_df.columns else ["all"]
 
            for lang in languages:
                for dim in self.dimensions:
                    sets = []
                    for judge in self.judges:
                        df = self.df_eval[judge][model]
                        if lang != "all" and "language" in df.columns:
                            df = df[df["language"] == lang]
                        sets.append(set(df.index.tolist()))
                    questions = list(set.intersection(*sets))
 
                    if len(questions) < 2:
                        results[model][lang][dim] = {
                            "alpha": None, "acceptable": None,
                            "note": "insufficient common items",
                        }
                        continue
 
                    matrix = []
                    for judge in self.judges:
                        df = self.df_eval[judge][model]
                        if lang != "all" and "language" in df.columns:
                            df = df[df["language"] == lang]
                        matrix.append(
                            df.loc[questions, dim].to_numpy(dtype=float)
                        )
 
                    reliability_data = np.array(matrix)
 
                    try:
                        alpha = krippendorff.alpha(
                            reliability_data=reliability_data,
                            level_of_measurement="ordinal",
                        )
                        results[model][lang][dim] = {
                            "alpha": round(float(alpha), 4),
                            "acceptable": bool(alpha >= 0.60),
                            "excellent": bool(alpha >= 0.80),
                            "n_items": len(common_questions),
                        }
                    except Exception as e:
                        results[model][lang][dim] = {
                            "alpha": None, "acceptable": None, "note": str(e),
                        }
 
        return dict(results)
    
    def _win_rate(self):
        """ Percentage where model X is majority-preferred. """
        results = defaultdict(dict)
        output_to_model = {1: self.models[0], 2: self.models[1], 3: self.models[2], 0: "no_preference"}
        majority_threshold = (len(self.judges) // 2) + 1

        all_votes = pd.concat(self.df_comp.values(), ignore_index=True)

        languages = all_votes["language"].unique() if "language" in all_votes.columns else ["all"]

        for lang in languages:
            sub = all_votes[all_votes["language"] == lang] if lang != "all" else all_votes

            vote_counts = defaultdict(lambda: defaultdict(int))
            for _, row in sub.iterrows():
                q = row["question"]
                preferred = output_to_model.get(
                    int(row["preferred_output"]) if pd.notna(row["preferred_output"]) else 0,
                    "no_preference"
                )
                vote_counts[q][preferred] += 1

            count_wins = defaultdict(int)
            n_prompts = len(vote_counts)

            for q, votes in vote_counts.items():
                best_model = max(votes, key=votes.get)
                if votes[best_model] >= majority_threshold:
                    count_wins[best_model] += 1
                else:
                    count_wins["no_winner"] += 1

            lang_results = {}
            for model in self.models + ["no_preference", "no_winner"]:
                wins = count_wins.get(model, 0)
                lang_results[model] = {
                    "wins": wins,
                    "total_prompts": n_prompts,
                    "win_rate": round(wins / n_prompts, 4) if n_prompts > 0 else None,
                }
            results[lang] = lang_results

        return dict(results)

    def delta_thematic_area(self):
        """ MOS difference per area: pinpoints fine-tuning impact. """
        results = defaultdict(dict)
        languages = self._get_all_languages()

        for lang in languages:
            frames = []
            for judge in self.judges:
                for model in self.models:
                    df = self.df_eval[judge][model].reset_index()
                    if "language" in df.columns and lang != "all":
                        df = df[df["language"] == lang]
                    df = df.copy()
                    df["model"] = model
                    df["judge"] = judge
                    frames.append(df)

            if not frames:
                continue

            combined = pd.concat(frames, ignore_index=True)

            area_col = next(
                (c for c in ["category_label", "thematic_area", "area"] if c in combined.columns),
                None,
            )
            if area_col is None:
                results[lang] = {"note": "no thematic area column found"}
                continue

            for area, grp in combined.groupby(area_col):
                area_results = {}
                for dim in self.dimensions:
                    mos_by_model = grp.groupby("model")[dim].mean()
                    m1 = mos_by_model.get(self.models[0], np.nan)
                    m2 = mos_by_model.get(self.models[1], np.nan)
                    m3 = mos_by_model.get(self.models[2], np.nan)
                    area_results[dim] = {
                        "mos_M1": round(float(m1), 4) if not np.isnan(m1) else None,
                        "mos_M2": round(float(m2), 4) if not np.isnan(m2) else None,
                        "mos_M3": round(float(m3), 4) if not np.isnan(m3) else None,
                        "delta_FT": round(float(m2 - m1), 4) if not (np.isnan(m1) or np.isnan(m2)) else None,
                        "delta_Quant": round(float(m3 - m2), 4) if not (np.isnan(m2) or np.isnan(m3)) else None,
                    }
                results[lang][area] = area_results
 
        return dict(results)

    def _metrics(self):
        return {
            "mos": self._mos,
            "friedman": self._friedman,
            "wilcoxon": self._wilcoxon_bonferroni,
            "cohen_r": self._cohen_r,
            "krippendorff": self._krippendorff,
            "win_rate": self._win_rate,
            "delta_thematic_area": self.delta_thematic_area,
        }

    def compute(self):
        results = {}
        for name, metric_fn in self._metrics().items():
            print(f"Computing {name}.")
            try:
                results[name] = metric_fn()
            except Exception as e:
                results[name] = {"error": str(e)}
        return results



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Metrics")
    parser.add_argument("--base", type=str, required=True, help="Base path evaluations.")
 
    args = parser.parse_args()
 
    base_path = args.base
    evaluator = LoMAEvaluation()
 
    judges = evaluator.get_judges()
    models = ["no_tuning", "q8_0", "q4_k_m"]
 
    eval_paths = {
        judge: {
            model: os.path.join(base_path, f"evaluation_qwen_3_5_{model}_dataset_qwen3_6_eval_{judge}.xlsx")
            for model in models
        }
        for judge in judges
    }
 
    comp_paths = {
        judge: os.path.join(base_path, f"comp_responses_{judge}.xlsx")
        for judge in judges
    }
 
    print("Computing metrics...")
    metrics = LoMAMetrics(
        eval_paths=eval_paths,
        comp_paths=comp_paths,
        judges=judges,
    ).compute()
 
    output_file = os.path.join(base_path, "metrics_results.json")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False, default=str)
 
    print(f"\nDone. Results saved to {output_file}")
    print(json.dumps(metrics, indent=2, default=str))