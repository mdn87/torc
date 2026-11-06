"""Thin local CLI adapters; shared adaptation policy lives in mirror.py."""

from .errors import InvalidInputError
from .mirror import project_response, render_context, render_text, resolve_settings
from .operator import load_json_object


def run_mirror_command(args):
    if args.mirror_command == "experiment":
        from .mirror_experiment import run_experiment

        return run_experiment(args.output_dir, now=args.now)
    data = load_json_object(args.input_file)
    action = args.mirror_command
    if action == "resolve":
        return resolve_settings(
            data.get("binding"), data.get("signals"), now=data.get("now"),
            ttl_seconds=data.get("ttl_seconds", 300),
        )
    if action == "context":
        return {"text": render_context(
            data.get("settings"), binding=data.get("binding"), now=data.get("now"),
        )}
    if action == "project":
        return project_response(
            data.get("settings"), data.get("result"), data.get("written"),
            data.get("response_id"), now=data.get("now"),
            target_chars=data.get("target_chars", 240),
        )
    if action == "text":
        return {"text": render_text(
            data.get("delivery"), binding=data.get("binding"),
            response_id=data.get("response_id"), now=data.get("now"),
        )}
    raise InvalidInputError(f"Unsupported Mirror action: {action}")
