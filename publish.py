import re
from pathlib import Path
import sys
import subprocess
from datetime import datetime
import shutil

def get_current_version():
    pyproject_path = Path("pyproject.toml")
    if not pyproject_path.exists():
        print("Error: pyproject.toml not found.")
        sys.exit(1)
    
    content = pyproject_path.read_text(encoding="utf-8")
    match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', content)
    if match:
        return match.group(1)
    
    init_path = Path("src/koggi/__init__.py")
    if init_path.exists():
        init_content = init_path.read_text(encoding="utf-8")
        match = re.search(r'__version__\s*=\s*"([^"]+)"', init_content)
        if match:
            return match.group(1)
            
    print("Error: Could not find current version.")
    sys.exit(1)

def bump_version(current, bump_type):
    parts = current.split('.')
    if len(parts) != 3:
        return current
        
    major, minor, patch = map(int, parts)
    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    elif bump_type == 'patch':
        patch += 1
    return f"{major}.{minor}.{patch}"

def update_version_files(new_version):
    pyproject_path = Path("pyproject.toml")
    content = pyproject_path.read_text(encoding="utf-8")
    new_content = re.sub(r'(?m)^version\s*=\s*"[^"]+"', f'version = "{new_version}"', content)
    pyproject_path.write_text(new_content, encoding="utf-8")
    print(f"Updated pyproject.toml -> {new_version}")

    init_path = Path("src/koggi/__init__.py")
    if init_path.exists():
        init_content = init_path.read_text(encoding="utf-8")
        new_init_content = re.sub(r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"', init_content)
        init_path.write_text(new_init_content, encoding="utf-8")
        print(f"Updated src/koggi/__init__.py -> {new_version}")

def update_changelog(new_version, description):
    changelog_path = Path("CHANGELOG.md")
    today = datetime.today().strftime("%Y-%m-%d")
    new_entry = f"## [{new_version}] - {today}\n\n- {description}\n\n"
    
    if changelog_path.exists():
        content = changelog_path.read_text(encoding="utf-8")
        if content.startswith("# Changelog"):
            parts = content.split("\n", 2)
            if len(parts) >= 3:
                header = parts[0] + "\n" + parts[1] + "\n"
                rest = parts[2]
                content = header + new_entry + rest
            else:
                content = content + "\n\n" + new_entry
        else:
            content = new_entry + content
    else:
        content = f"# Changelog\n\nAll notable changes to this project will be documented in this file.\n\n{new_entry}"
        
    changelog_path.write_text(content, encoding="utf-8")
    print("Updated CHANGELOG.md")

def run_publish(target):
    print(f"\n🚀 Running bash pp.sh {target}...")
    bash_cmd = "bash"
    if not shutil.which("bash"):
        git_bash = Path(r"C:\Program Files\Git\bin\bash.exe")
        if git_bash.exists():
            bash_cmd = str(git_bash)
        else:
            print("Warning: bash not found in PATH or Git default directory. Trying to run pp.sh directly...")
            
    try:
        subprocess.run([bash_cmd, "pp.sh", target], check=True)
        print("Publish script completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error during publishing: {e}")
        sys.exit(1)

def git_commit_and_tag(version, description):
    try:
        if not Path(".git").exists():
            return
        subprocess.run(["git", "add", "pyproject.toml", "src/koggi/__init__.py", "CHANGELOG.md"], check=True)
        commit_msg = f"Release v{version}: {description}"
        subprocess.run(["git", "commit", "-m", commit_msg], check=True)
        subprocess.run(["git", "tag", f"v{version}"], check=True)
        print(f"Git commit and tag v{version} created.")
        print("👉 Run 'git push && git push --tags' to share changes.")
    except subprocess.CalledProcessError as e:
        print(f"Git operations failed: {e}")

def main():
    current_version = get_current_version()
    print(f"Current Version: {current_version}")
    
    # Check if arguments are provided
    if len(sys.argv) > 1:
        # Argument parsing
        import argparse
        parser = argparse.ArgumentParser(description="Automate package release.")
        parser.add_argument("--bump", choices=["patch", "minor", "major"], default="patch", help="Version bump type (default: patch)")
        parser.add_argument("--desc", required=True, help="Release description for changelog and commit message")
        parser.add_argument("--target", choices=["main", "test", "none"], default="main", help="Publish target: main (PyPI), test (TestPyPI), or none (default: main)")
        args = parser.parse_args()
        
        bump = args.bump
        desc = args.desc
        target = args.target
    else:
        # Interactive mode
        try:
            bump_choice = input("Select version bump [1: patch, 2: minor, 3: major] (default: 1): ").strip()
            if bump_choice == '2':
                bump = 'minor'
            elif bump_choice == '3':
                bump = 'major'
            else:
                bump = 'patch'
                
            new_version = bump_version(current_version, bump)
            print(f"Target Version: {new_version}")
            
            desc = input("Enter release description: ").strip()
            if not desc:
                print("Error: Description is required.")
                sys.exit(1)
                
            target_choice = input("Publish target [1: PyPI (main), 2: TestPyPI (test), 3: None (build-only)] (default: 1): ").strip()
            if target_choice == '2':
                target = 'test'
            elif target_choice == '3':
                target = 'none'
            else:
                target = 'main'
        except KeyboardInterrupt:
            print("\nCancelled.")
            sys.exit(0)
            
    new_version = bump_version(current_version, bump)
    print(f"\nProceeding to release v{new_version}...")
    
    # 1. Update files
    update_version_files(new_version)
    
    # 2. Update changelog
    update_changelog(new_version, desc)
    
    # 3. Publish if target selected
    if target != 'none':
        run_publish(target)
        
    # 4. Git operations
    git_commit_and_tag(new_version, desc)
    print(f"\n🎉 Successfully released v{new_version}!")

if __name__ == "__main__":
    main()
