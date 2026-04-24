#!/bin/bash
python -m app.services.agent.agent reply --stu-message "$1" --chat-id "${2:-}" --history "${3:-}" --model "${4:-}" --json-output