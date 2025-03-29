import os
import json
import questionary
import requests
from io import BytesIO
import zipfile
from pathlib import Path

from embeddings.embed import embed_context
from rag import rag_query  # We'll call rag_query(context_name, user_query)

GITHUB_API_URL = "https://api.github.com"
ORGANIZATION = "cisco-sbg"
CONTEXTS_JSON = "contexts.json"

def load_contexts():
    if os.path.exists(CONTEXTS_JSON):
        with open(CONTEXTS_JSON, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_contexts(ctx):
    with open(CONTEXTS_JSON, "w", encoding="utf-8") as f:
        json.dump(ctx, f, ensure_ascii=False, indent=2)

def get_github_token():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN not set.")
    return token

def get_headers():
    return {
        "Authorization": f"token {get_github_token()}",
        "Accept": "application/vnd.github.v3+json"
    }

def search_repos(organization, query):
    """Return up to 20 repos matching `query` in the org."""
    headers = get_headers()
    params = {
        "q": f"{query} org:{organization}",
        "per_page": "20"
    }
    url = f"{GITHUB_API_URL}/search/repositories"
    resp = requests.get(url, headers=headers, params=params)
    if resp.status_code == 200:
        data = resp.json()
        return data.get("items", [])
    else:
        print(f"Error searching: {resp.status_code} {resp.reason}")
        return []

def fetch_repo_zip(repo_full_name, context_name):
    """
    Download the repo as a zip to ./repos/<context_name>/<repo_name>.
    Return the path we extracted to, or None if fail.
    """
    print(f"Fetching: {repo_full_name} for context '{context_name}'")
    headers = get_headers()
    zip_url = f"{GITHUB_API_URL}/repos/{repo_full_name}/zipball"
    r = requests.get(zip_url, headers=headers, stream=True)
    if r.status_code == 200:
        repo_name = repo_full_name.split("/", 1)[1]
        target_dir = Path("repos") / context_name / repo_name
        target_dir.mkdir(parents=True, exist_ok=True)

        zip_data = BytesIO(r.content)
        with zipfile.ZipFile(zip_data, 'r') as zip_ref:
            zip_ref.extractall(str(target_dir))

        print(f"Extracted {repo_full_name} -> {target_dir}")
        return target_dir
    else:
        print(f"Failed to fetch {repo_full_name}: {r.status_code} {r.reason}")
        return None

def embed_repos_in_context(context_name, contexts):
    """
    1) Ask user for a search term, find up to 20 repos
    2) Let user pick which repos to embed
    3) Download + embed each selected repo
    4) Update contexts
    """
    query = questionary.text("Search term for repos (e.g. 'sfcn')?").ask()
    results = search_repos(ORGANIZATION, query)
    if not results:
        print("No repos found or an error occurred.")
        return

    label_map = {}
    for r in results:
        label = f"{r['full_name']} (★{r.get('stargazers_count',0)})"
        label_map[label] = r

    selected_labels = questionary.checkbox(
        "Select repos to embed:",
        choices=list(label_map.keys())
    ).ask()
    if not selected_labels:
        print("No repos selected.")
        return

    newly_embedded = []
    for lbl in selected_labels:
        r = label_map[lbl]
        full_name = r["full_name"]
        already_in_context = context_name in contexts and (full_name in contexts[context_name])
        if already_in_context:
            print(f"Repo {full_name} is already in context '{context_name}', skipping.")
            continue

        extracted_path = fetch_repo_zip(full_name, context_name)
        if not extracted_path:
            print("Download failed, skipping embed for this repo.")
            continue

        # embed
        embed_context(context_name, str(extracted_path))

        # add to contexts
        if context_name not in contexts:
            contexts[context_name] = []
        contexts[context_name].append(full_name)
        newly_embedded.append(full_name)

    if newly_embedded:
        save_contexts(contexts)
        print(f"Embedded {len(newly_embedded)} repos in context '{context_name}'. Updated contexts.")

def main():
    contexts = load_contexts()

    while True:
        action = questionary.select(
            "Main Menu",
            choices=[
                "Select or create context",
                "View existing contexts",
                "Exit"
            ]
        ).ask()

        if action == "View existing contexts":
            if not contexts:
                print("No contexts exist yet.")
            else:
                for ctx, repos in contexts.items():
                    print(f"\nContext: {ctx}")
                    for r in repos:
                        print(f"  - {r}")

        elif action == "Select or create context":
            # If no contexts exist, ask them if they want to create new or proceed with no context
            if not contexts:
                choice = questionary.select(
                    "No contexts exist. Create new or proceed with none?",
                    choices=["Create new context", "Proceed with no context"]
                ).ask()
                if choice == "Create new context":
                    context_name = questionary.text("Enter new context name:").ask()
                else:
                    context_name = None
            else:
                # If contexts exist, user can pick an existing one, create new, or proceed with no context
                existing_ctx_list = list(contexts.keys())
                chosen = questionary.select(
                    "Pick an existing context or create new / no context:",
                    choices=existing_ctx_list + ["Create new context", "Proceed with no context"]
                ).ask()
                if chosen == "Create new context":
                    context_name = questionary.text("Enter context name:").ask()
                elif chosen == "Proceed with no context":
                    context_name = None
                else:
                    context_name = chosen

            # Ask if user wants to embed additional repos (only if we have a context_name)
            if context_name:
                add_more = questionary.confirm(
                    f"Embed additional repos into context '{context_name}'?"
                ).ask()
                if add_more:
                    embed_repos_in_context(context_name, contexts)

            # Now let's see if user wants to ask a query
            ask_query = questionary.confirm("Do you want to ask a query now?").ask()
            if ask_query:
                user_query = questionary.text("Enter your query:").ask()
                if user_query.strip():
                    answer = rag_query(context_name, user_query)
                    print(f"\nRAG-based answer:\n{answer}\n")
                else:
                    print("No query provided. Skipping.")
            else:
                print("Skipping query for now.")

        elif action == "Exit":
            print("Goodbye.")
            break

if __name__ == "__main__":
    main()
