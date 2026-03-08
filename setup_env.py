#!/usr/bin/env python3
import shutil
import os
from pathlib import Path

def main():
    root_dir = Path(__file__).parent
    env_example = root_dir / ".env.example"
    env_file = root_dir / ".env"

    print("=== PyOpenClaw Configuration Setup ===")
    
    if not env_example.exists():
        print("Error: .env.example not found.")
        return

    if env_file.exists():
        print("A .env file already exists.")
        choice = input("Do you want to overwrite it? (y/N): ").strip().lower()
        if choice != 'y':
            print("Skipping .env creation.")
            return
    
    print("Creating .env from template...")
    shutil.copy(env_example, env_file)
    print(f"Created {env_file}")
    
    print("\nNow let's configure your API keys.")
    print("Press Enter to skip any provider you don't use.")
    
    updates = {}
    
    # OpenAI
    openai_key = input("Enter OpenAI API Key: ").strip()
    if openai_key:
        updates["OPENAI_API_KEY"] = openai_key
        
    # Anthropic
    anthropic_key = input("Enter Anthropic API Key: ").strip()
    if anthropic_key:
        updates["ANTHROPIC_API_KEY"] = anthropic_key
        
    # Gemini
    gemini_key = input("Enter Gemini API Key: ").strip()
    if gemini_key:
        updates["GEMINI_API_KEY"] = gemini_key
        
    # MiniMax
    minimax_key = input("Enter MiniMax API Key: ").strip()
    if minimax_key:
        updates["MINIMAX_API_KEY"] = minimax_key
        
    minimax_group = input("Enter MiniMax Group ID (optional): ").strip()
    if minimax_group:
        updates["MINIMAX_GROUP_ID"] = minimax_group

    # Update the file
    if updates:
        content = env_file.read_text()
        for key, value in updates.items():
            # Simple replacement of placeholder lines
            # Assumes format KEY=value or # KEY=value
            if f"{key}=" in content:
                # Replace existing line (commented or not)
                import re
                content = re.sub(f"^#? ?{key}=.*", f"{key}={value}", content, flags=re.MULTILINE)
            else:
                # Append if not found
                content += f"\n{key}={value}"
        
        env_file.write_text(content)
        print("\nConfiguration saved to .env")
    else:
        print("\nNo changes made to .env")

    print("\nSetup complete! You can edit .env manually at any time.")

if __name__ == "__main__":
    main()
