"""Only fixed outcome labels; never filenames, documents, identities or URLs."""

from opentelemetry import metrics

meter = metrics.get_meter("happy.reliability")
parser_attempts = meter.create_counter("happy.parser.attempts")
parser_duration = meter.create_histogram("happy.parser.duration_seconds", unit="s")
scanner_results = meter.create_counter("happy.scanner.results")
scanner_duration = meter.create_histogram("happy.scanner.duration_seconds", unit="s")
