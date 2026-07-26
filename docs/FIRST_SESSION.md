# First working session

The starter repository has already been assembled. Your first session should focus on understanding and verifying it rather than adding features immediately.

## Session outcome

By the end, you should be able to:

- Explain every column in `data/sample_chain.csv`
- Run the automated tests
- Launch the dashboard
- Identify why the sample contains midpoint anomalies
- Explain why a midpoint anomaly is not automatically executable
- Make and push your first meaningful Git commit

## Checklist

- [ ] Install Python, GitHub Desktop, and VS Code
- [ ] Create and activate `.venv`
- [ ] Run `pip install -e ".[dev]"`
- [ ] Run `pytest`
- [ ] Run `python -m arblens data/sample_chain.csv`
- [ ] Run `streamlit run dashboard/app.py`
- [ ] Read `src/arblens/detection.py`
- [ ] Create the public GitHub repository
- [ ] Commit and publish the reviewed starter

## First code change to make personally

After the baseline works, add one new test that confirms a normal decreasing call-price chain produces no strike-monotonicity violation. This is small, understandable, and creates an authentic first contribution.
