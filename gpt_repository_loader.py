import subprocess
import os
import sys
import re


def list_github_managed_files(repo_path, git_ignore_path, gpt_ignore_path):
    def parse_gitignore_pattern(pattern):
        if pattern.startswith("/"):
            pattern = "^" + pattern[1:]
        elif "/" in pattern and not pattern.startswith("*"):
            pattern = "(^|/)" + pattern
        else:
            pattern = "(^|/|.*/)" + pattern

        if pattern.endswith("/"):
            pattern += ".*"
        elif pattern.endswith("/*"):
            pattern = pattern[:-2] + "(/.*)?$"
        elif not pattern.endswith("$") and "*" not in pattern:
            pattern += "$"
        elif not pattern.endswith("$"):
            pattern += "(/.*)?$"

        return pattern.replace(".**", ".+").replace("*", "[^/]*").replace("?", ".")

    def should_ignore(path, ignore_patterns):
        if path.startswith(".git") or "/.git/" in path:
            return True

        for pattern in ignore_patterns:
            if pattern.search(path):
                return True
        return False

    def read_ignore_file(ignore_path):
        if not os.path.exists(ignore_path):
            return []
        with open(ignore_path, "r") as f:
            lines = f.readlines()
            patterns = [
                line.strip()
                for line in lines
                if line.strip() and not line.startswith("#")
            ]
        return [re.compile(parse_gitignore_pattern(p)) for p in patterns]

    ignore_patterns = read_ignore_file(git_ignore_path)
    ignore_patterns += read_ignore_file(gpt_ignore_path)
    managed_files = []

    for root, dirs, files in os.walk(repo_path):
        rel_root = os.path.relpath(root, repo_path)
        rel_root = "" if rel_root == "." else rel_root + "/"

        dirs[:] = [
            d for d in dirs if not should_ignore(rel_root + d + "/", ignore_patterns)
        ]

        for file in files:
            rel_path = rel_root + file
            if not should_ignore(rel_path, ignore_patterns):
                managed_files.append(rel_path)

    return managed_files


def remove_extra_whitespace(text):
    text = re.sub(r"^\s+|\s+$", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s+", " ", text)
    return text


def remove_comments(text):
    text = re.sub(r"#.*", "", text)
    text = re.sub(r"//.*|/\*[\s\S]*?\*/", "", text)
    return text


def remove_tags(text):
    text = re.sub(r"<[^>]+>", "", text)
    return text


def minimize_text(text):
    text = remove_extra_whitespace(text)
    text = remove_comments(text)
    text = remove_tags(text)
    return text


def process_repository(repo_root, repo_path, output_file):
    git_ignore_path = os.path.join(repo_root, ".gitignore")
    HERE = os.path.dirname(os.path.abspath(__file__))
    gpt_ignore_path = os.path.join(HERE, ".gptignore")

    managed_files = list_github_managed_files(
        repo_path, git_ignore_path, gpt_ignore_path
    )
    for file_path in managed_files:
        file_path = os.path.join(repo_path, file_path)
        with open(file_path, "r", errors="ignore") as file:
            contents = file.read()
        minimized_contents = minimize_text(contents)
        output_file.write("-" * 4 + "\n")
        output_file.write(f"{file_path}\n")
        output_file.write(f"{minimized_contents}\n")


def get_repo_root(path):
    try:
        repo_root = (
            subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=path)
            .strip()
            .decode("utf-8")
        )
        return repo_root
    except subprocess.CalledProcessError:
        print("Error: Not a git repository.")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(
            "Usage: python git_to_text.py /path/to/git/repository [-p /path/to/preamble.txt] [-o /path/to/output_file.txt]"
        )
        sys.exit(1)
    repo_path = sys.argv[1]
    repo_root = get_repo_root(repo_path)

    preamble_file = None
    if "-p" in sys.argv:
        preamble_file = sys.argv[sys.argv.index("-p") + 1]

    output_file_path = "output.txt"
    if "-o" in sys.argv:
        output_file_path = sys.argv[sys.argv.index("-o") + 1]

    with open(output_file_path, "w") as output_file:
        if preamble_file:
            with open(preamble_file, "r") as pf:
                preamble_text = pf.read()
                output_file.write(f"{preamble_text}\n")
        else:
            output_file.write(
                "The following text is a Git repository with code. The structure of the text are sections that begin with ----, followed by a single line containing the file path and file name, followed by a variable amount of lines containing the file contents. The text representing the Git repository ends when the symbols --END-- are encountered. Any further text beyond --END-- are meant to be interpreted as instructions using the aforementioned Git repository as context.\n"
            )
        process_repository(repo_root, repo_path, output_file)
    with open(output_file_path, "a") as output_file:
        output_file.write("--END--")
    print(f"Repository contents written to {output_file_path}.")
