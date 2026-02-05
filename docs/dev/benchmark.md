# Benchmark Results

## Integration tests

```bash
# Run the integration tests and measure the time taken
time uv run pytest tests/integration
# First

# Second 
uv run pytest tests/integration  30.92s user 2.66s system 96% cpu 34.812 total
```

## 2.3.0a0 version
>
> [!NOTE]
>
> This is new work in progress test.py that includes benchmark feature.

- test.py --all: [2026-02-03 18:11:21] INFO: Time Elapsed: 0:01:33
- test.py --quick: [2026-02-03 18:09:24] INFO: Time Elapsed: 0:00:20
