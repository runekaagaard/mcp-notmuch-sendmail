#!/usr/bin/env python3
import argparse
import json
import os
from pathlib import Path

def draft_cmd(args):
    # Import after env vars are set
    from sendmail import create_draft
    """Handle the draft subcommand"""
    markdown_text = args.markdown_file.read_text()
    draft = create_draft(
        markdown_text=markdown_text,
        metadata={
            'subject': args.subject,
            'to': args.to,
            'cc': args.cc or [],
            'bcc': args.bcc or []
        }
    )
    print(f"Created drafts:\n- {draft['markdown']} (edit this)\n- {draft['html']} (preview)")

def load_config(config_path: Path, tool_title: str) -> None:
    """Load configuration and set environment variables"""
    config = json.loads(config_path.read_text())
    
    try:
        env_vars = config["mcpServers"][tool_title]["env"]
        for key, value in env_vars.items():
            os.environ[key] = str(value)
    except KeyError as e:
        raise ValueError(f"Invalid config structure - missing {e} in config file")

def main():
    parser = argparse.ArgumentParser(description='Email client CLI')
    parser.add_argument('-c', '--config-file', type=Path, required=True,
                       help='Path to config JSON file')
    parser.add_argument('-t', '--tool-title', required=True,
                       help='Tool title from config')
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # draft subcommand
    draft_parser = subparsers.add_parser('draft', help='Create email draft from markdown file')
    draft_parser.add_argument('-m', '--markdown-file', type=Path, required=True,
                            help='Path to markdown file')
    draft_parser.add_argument('-s', '--subject', required=True,
                            help='Email subject')
    draft_parser.add_argument('-t', '--to', required=True, nargs='+',
                            help='Recipient email addresses')
    draft_parser.add_argument('-c', '--cc', nargs='+',
                            help='CC email addresses')
    draft_parser.add_argument('-b', '--bcc', nargs='+',
                            help='BCC email addresses')
    draft_parser.set_defaults(func=draft_cmd)

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
        
    # Load config before executing any commands
    load_config(args.config_file, args.tool_title)
    
    # Execute the command
    args.func(args)

if __name__ == '__main__':
    main()
