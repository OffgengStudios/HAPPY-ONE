"""Bounded operational counters. Never use submitted values as metric labels."""

from opentelemetry import metrics

meter = metrics.get_meter("happy.intake")
participant_received = meter.create_counter("participant_intakes_received")
participant_completed = meter.create_counter("participant_intakes_completed")
employer_received = meter.create_counter("employer_intakes_received")
employer_converted = meter.create_counter("employer_intakes_converted")
duplicate_reviews = meter.create_counter("duplicate_reviews_opened")
scan_failures = meter.create_counter("document_scan_failures")
