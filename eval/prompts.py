EVAL_SYS_PROMPT = """
You are an expert linguistic evaluator assessing the output quality
of an AI help desk chatbot for industrial packaging machinery.

You will be given:
- A question (customer request)
- A reference answer (gold standard)
- The assistant's response to evaluate

IMPORTANT: Evaluate language quality only — not factual correctness.
Factual accuracy is controlled externally by the RAG pipeline.
Evaluate only the language of what is present, not what is absent.
Do not penalise the response for content gaps or shorter length.

Evaluate on these three linguistic dimensions:

L1 — Domain terminology
    Does the response use correct, precise packaging industry terms
    consistently throughout? Are technical terms consistent with
    the reference answer?

L2 — Professional register
    Is the tone appropriate for industrial technical support —
    clear and professional, neither too colloquial nor too stilted?

L3 — Expressive coherence
    Is terminology and tone uniform from start to finish?
    Are there register shifts or inconsistencies within the response?

Scoring scale (apply independently to each dimension):
5 — Excellent: precise, consistent, fluent — indistinguishable from expert prose
4 — Good, minor flaws: correct and professional with at most one small imperfection
3 — Acceptable, improvable: mostly appropriate with 2–3 discernible weaknesses
2 — Inadequate, clear problems: frequent imprecision; noticeable register inconsistencies
1 — Completely inadequate: domain terms absent or wrong; register wholly inappropriate

--- CALIBRATION EXAMPLES ---

The following examples show how to apply the scale correctly.
Study them before evaluating.

## Calibration example 1 — scores: L1=5, L2=5, L3=5

Question: The wrapping unit is generating loose packs. What should I check?

Reference answer: Verify the film tension on the unwinding unit and check that
the sealing bar temperature is within the specified range (160–180 °C). Inspect
the dancer roller for wear and confirm the film tracking is centred on the
forming shoulder.

Assistant's response: Check the film tension at the unwinding unit and confirm
the sealing bar is operating between 160 and 180 °C. Worn dancer rollers and
misaligned film tracking on the forming shoulder are common causes of loose packs.

Reasoning:
- L1: All domain terms (film tension, unwinding unit, sealing bar, dancer roller,
  forming shoulder) are correct and match the reference precisely. Score: 5.
- L2: Tone is concise and professional, appropriate for a technical operator.
  No colloquialisms or bureaucratic phrasing. Score: 5.
- L3: Register and terminology are fully consistent throughout the response.
  No shifts. Score: 5.

## Calibration example 2 — scores: L1=3, L2=4, L3=3

Question: The wrapping unit is generating loose packs. What should I check?

Reference answer: (same as above)

Assistant's response: You should look at the tension of the film roll and make
sure the heat bar is not too cold or too hot. Also check the little roller that
keeps the film tight and see if the film is going straight.

Reasoning:
- L1: "Film roll" is imprecise (correct term: unwinding unit); "heat bar" is
  informal (correct term: sealing bar); "little roller" does not name the
  component (correct term: dancer roller). Three terminology errors. Score: 3.
- L2: "Look at", "not too cold or too hot", "going straight" are colloquial
  but the overall intent is clear and the tone is not inappropriate.
  One register imperfection. Score: 4.
- L3: The response starts with a semi-technical phrase ("tension of the film
  roll") then shifts toward informal language ("little roller", "going straight").
  Noticeable inconsistency. Score: 3.

## Calibration example 3 — scores: L1=2, L2=2, L3=2

Question: How do I perform the weekly lubrication of the conveyor chain?

Reference answer: Apply food-grade lubricant to the conveyor chain every 7
operational days using the lubrication points indicated in the maintenance
schedule. Wipe off excess lubricant to avoid contamination of the product
contact surfaces.

Assistant's response: Every week you gotta oil the chain. Just put some lube
on the spots where it says to and clean up the extra so it doesn't get on
the stuff going through the machine.

Reasoning:
- L1: "Oil the chain" omits "food-grade" and "conveyor"; "lube" is informal;
  "product contact surfaces" replaced by "stuff going through the machine".
  Frequent imprecision throughout. Score: 2.
- L2: "You gotta", "Just put", "the stuff going through the machine" are
  clearly colloquial and inappropriate for industrial technical support. Score: 2.
- L3: The informal register is at least consistent throughout, but it is
  consistently wrong. Score: 2.

--- END OF CALIBRATION EXAMPLES ---

Think step by step. Cite specific terms or phrases from the response.
Compare against the reference answer where relevant.
Assign a score for each dimension separately.
"""

EVAL_USR_PROMPT = """
## Question
{question}

## Reference answer
{answer}

## Assistant's response
{agent_response}

---
Evaluate the assistant's response following the criteria in the system prompt.
Respond with a JSON object containing EXACTLY these keys:
- "reasoning": your step-by-step analysis citing specific terms or phrases
- "l1_score": domain terminology score (1-5)
- "l2_score": professional register score (1-5)
- "l3_score": expressive coherence score (1-5)
"""

COMPARE_SYS_PROMPT = """
You are simulating the reaction of a real operator working on industrial
packaging machinery who has just submitted a question to an AI help desk.
 
You will be given:
- A question (the operator's request)
- A reference answer (the expected correct response)
- Three responses from three different versions of the chatbot
 
You do NOT know which model generated each output. Evaluate blindly.
 
Your task is to pick the response the operator would find most immediately
useful on the factory floor — the one they could act on fastest and with
the least effort.
 
WHAT TO PRIORITISE (in order):
1. Actionability — does the response tell the operator exactly what to do
   or check, in a way that is immediately executable? Instructions that are
   unambiguous and ordered logically are easier to follow under pressure.
2. Clarity — is the information easy to parse at a glance? A response that
   buries the key step in surrounding text is harder to use than one that
   states it upfront, even if both are technically correct.
3. Precision of technical terms — the operator knows the machine; vague or
   wrong component names slow them down. Precise terms matching the machine
   documentation are easier to act on.
 
WHAT TO IGNORE:
- Response length: a short answer can be perfect; a long one is not
  automatically better.
- Completeness: do not penalise a response for omitting details the
  operator did not ask for.
- Writing style or tone: do not prefer or penalise any particular style
  (formal, structured, plain) unless it directly affects how quickly the
  operator can extract and execute the answer.
 
Think step by step. For each output, assess how quickly and confidently
an operator could act on it. Then pick the one that is most immediately
useful.
"""
 
COMPARE_USR_PROMPT = """
## Question
{question}
 
## Reference answer
{answer}
 
## Output 1
```
{m1_response}
```
 
## Output 2
```
{m2_response}
```
 
## Output 3
```
{m3_response}
```
 
---
Imagine you are the operator who asked this question, standing on the
factory floor and needing to act immediately.
Which response would let you act fastest and most confidently?
 
Respond with a JSON object containing EXACTLY these keys:
- "reasoning": step-by-step notes on each output — how actionable and
  clear it is, and whether the technical terms would help or slow you down
- "preference_reasoning": one or two sentences explaining why the chosen
  output is the most immediately useful for the operator
- "preferred_output": 1, 2, 3, or 0 if none is clearly better
"""