
import os
import json
from collections import defaultdict
from pathlib import Path

IGNORE_DIRS = {
    "node_modules",
    ".git",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".venv",
    "venv",
    ".idea",
    ".vscode"
}

EXTENSION_LANG = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript React",
    ".jsx": "React",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++",
    ".c": "C",
    ".php": "PHP",
    ".rb": "Ruby",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".json": "JSON",
    ".yml": "YAML",
    ".yaml": "YAML",
    ".sh": "Shell",
    ".md": "Markdown"
}


def format_size(size):
    for unit in ["B","KB","MB","GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024


def generate_tree(root):

    for root_dir, dirs, files in os.walk(root):

        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        level = root_dir.replace(root, "").count(os.sep)

        indent = "│   " * level
        print(f"{indent}├── {os.path.basename(root_dir)}/")

        subindent = "│   " * (level + 1)

        for f in files:
            print(f"{subindent}├── {f}")


def analyze_languages(root):

    stats = defaultdict(int)

    for root_dir, dirs, files in os.walk(root):

        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:

            ext = Path(file).suffix.lower()

            if ext in EXTENSION_LANG:
                stats[EXTENSION_LANG[ext]] += 1

    return stats


def project_size(root):

    total = 0

    for root_dir, dirs, files in os.walk(root):

        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for f in files:

            path = os.path.join(root_dir, f)

            try:
                total += os.path.getsize(path)
            except:
                pass

    return total


def find_dependencies(root):

    deps = []

    package = Path(root) / "package.json"
    requirements = Path(root) / "requirements.txt"

    if package.exists():

        try:
            data = json.loads(package.read_text())

            deps += list(data.get("dependencies", {}).keys())
            deps += list(data.get("devDependencies", {}).keys())

        except:
            pass

    if requirements.exists():

        deps += requirements.read_text().splitlines()

    return deps


def find_important_files(root):

    targets = [
        "README.md",
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Dockerfile",
        "docker-compose.yml",
        ".env.example"
    ]

    found = []

    for t in targets:

        p = Path(root) / t

        if p.exists():
            found.append(t)

    return found


def main():

    root = os.getcwd()

    print("\n===== PROJECT ANALYSIS =====\n")

    size = project_size(root)
    print("Project Size:", format_size(size))

    print("\n===== LANGUAGES =====")

    languages = analyze_languages(root)

    for lang, count in languages.items():
        print(f"{lang}: {count} files")

    print("\n===== DEPENDENCIES =====")

    deps = find_dependencies(root)

    if deps:
        for d in deps:
            print("-", d)
    else:
        print("None detected")

    print("\n===== IMPORTANT FILES =====")

    important = find_important_files(root)

    for f in important:
        print("-", f)

    print("\n===== DIRECTORY STRUCTURE =====\n")

    generate_tree(root)


if __name__ == "__main__":
    main()