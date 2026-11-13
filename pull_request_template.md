## ITMO DDE final project / homework

### What was done
- [ ] Raw dataset hosted in Google Drive, repository links to it, link readable by reviewer
- [ ] Data ingest from Google Drive tested
- [ ] EDA notebook executed and rendered
- [ ] Package CLI (`leo-etl --help`, `leo-etl run`) works
- [ ] SQLite and data-integrity checks pass
- [ ] Static + interactive plots committed or linked
- [ ] README + dependencies + tests in place

### How to test

```bash
python -m pip install -e '.[dev,notebook]'
leo-etl generate
leo-etl run
python -m pytest -q
```

### Before merge
- [ ] Hermie App connected
- [ ] Instructor requested as Reviewer
- [ ] Hermie review received
- [ ] Instructor review received

Please do not merge until both reviews are complete.
