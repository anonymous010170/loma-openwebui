## Agno-Agent Evaluation

This folder contains `evaluate.py`, a script to evaluate [Agno](https://github.com/agno-agi/agno) agent reliability.

### Script Behaviour

1. Reads an `.xlsx` file containing the queries to evaluate.
2. Iterates over each query in the specified column.
3. Runs the agent on each query.
4. Saves the results to a new `.xlsx` file with an `agent_response` column appended.

### Usage

```bash
make test INPUT_FILE=<input_file> EVAL_COLUMN=<column_name> OUTPUT_FILE=<output_file>
```
or

```bash
python3 evaluate.py --file <input_file> --column <column_name> --output <output_file>
```

### Arguments

| Argument | Description |
|----------|-------------|
| `--file` | Input Excel file name (without `.xlsx` extension) |
| `--column` | Column name containing the queries to evaluate |
| `--output` | Output Excel file name (without `.xlsx` extension) |

### Example

```bash
make test INPUT_FILE=questions EVAL_COLUMN=query OUTPUT_FILE=results
```

or

```bash
python3 evaluate.py --file questions --column query --output results
```

---

### Notes
- **This evaluation script starts only if other services are running**.
- Both the input and output files are expected to be located in this folder.
- If an error occurs while processing a query, it is caught and stored in an `error` column in the output file rather than interrupting the run.