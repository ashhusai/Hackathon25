# import os
# import json
# import questionary
# import requests
# from io import BytesIO
# import zipfile
# from pathlib import Path

# # For multi-GPU embedding (the code we previously wrote)
# #from multi_gpu_embed import multiprocess_embed

# # The GitHub API base
# GITHUB_API_URL = "https://api.github.com"
# ORGANIZATION = "cisco-sbg"

# # Path to store our persistent contexts
# CONTEXTS_JSON = "contexts.json"


# def load_contexts():
#     """Load the contexts dictionary from a JSON file if it exists."""
#     if os.path.exists(CONTEXTS_JSON):
#         with open(CONTEXTS_JSON, "r", encoding="utf-8") as f:
#             return json.load(f)
#     return {}

# def save_contexts(contexts):
#     """Save the contexts dictionary to a JSON file."""
#     with open(CONTEXTS_JSON, "w", encoding="utf-8") as f:
#         json.dump(contexts, f, ensure_ascii=False, indent=2)

# def get_github_token():
#     token = os.getenv("GITHUB_TOKEN")
#     if not token:
#         raise ValueError("Please set GITHUB_TOKEN in environment variables.")
#     return token

# def get_headers():
#     return {
#         "Authorization": f"token {get_github_token()}",
#         "Accept": "application/vnd.github.v3+json",
#     }

# def search_repos(organization, query):
#     """Search up to 20 repos in the organization matching `query`."""
#     headers = get_headers()
#     # We add a parameter `per_page=20` to limit the results
#     params = {
#         "q": f"{query} org:{organization}",
#         "per_page": "20"
#     }
#     url = f"{GITHUB_API_URL}/search/repositories"
#     response = requests.get(url, headers=headers, params=params)
#     if response.status_code == 200:
#         data = response.json()
#         return data.get("items", [])
#     else:
#         print(f"Error: {response.status_code} - {response.reason}")
#         return []

# def fetch_and_extract_repo(repo_full_name, context_name):
#     """
#     Download the ZIP for a repo 'cisco-sbg/some-repo' and extract to Repos/<context_name>/<some-repo>.
#     """
#     headers = get_headers()
#     # e.g. https://api.github.com/repos/cisco-sbg/<repo>/zipball
#     zip_url = f"{GITHUB_API_URL}/repos/{repo_full_name}/zipball"
#     print(f"Fetching: {zip_url}")
#     response = requests.get(zip_url, headers=headers)
#     if response.status_code == 200:
#         zip_data = BytesIO(response.content)
#         extract_path = Path("repos") / context_name / repo_full_name.split("/", 1)[1]
#         extract_path.mkdir(parents=True, exist_ok=True)
#         with zipfile.ZipFile(zip_data, "r") as zip_ref:
#             zip_ref.extractall(str(extract_path))
#         print(f"Extracted {repo_full_name} -> {extract_path}")
#     else:
#         print(f"Failed to fetch {repo_full_name}: {response.status_code} {response.reason}")

# def main():
#     # Load the contexts dictionary
#     contexts = load_contexts()

#     while True:
#         action = questionary.select(
#             "Main Menu: Choose an action",
#             choices=[
#                 "View existing contexts",
#                 "Create / update context with new repos",
#                 "Exit",
#             ],
#         ).ask()

#         if action == "View existing contexts":
#             if not contexts:
#                 print("No contexts exist yet. Please create one by embedding repos first.")
#             else:
#                 # Show each context with the repos in it
#                 for ctx_name, repos_list in contexts.items():
#                     print(f"\nContext: {ctx_name}")
#                     if repos_list:
#                         for r in repos_list:
#                             print(f" - {r}")
#                     else:
#                         print("  (No repos embedded yet.)")

#         elif action == "Create / update context with new repos":
#             # 1) ask user for search term
#             query = questionary.text("Enter a search term for the repos (e.g. 'sfcn')?").ask()
#             repos_found = search_repos(ORGANIZATION, query)
#             if not repos_found:
#                 print("No matching repos found or an error occurred.")
#                 continue

#             # 2) let them pick from up to 20 results
#             repo_choices = {f"{r['full_name']}  [stars: {r['stargazers_count']}]": r for r in repos_found}
#             to_embed = questionary.checkbox("Select repos to embed:", choices=repo_choices.keys()).ask()
#             if not to_embed:
#                 print("No repos selected.")
#                 continue

#             # 3) ask user for context name
#             # either pick existing or type a new one
#             existing_contexts = list(contexts.keys())
#             new_or_existing = questionary.select(
#                 "Select or create a context name:",
#                 choices=existing_contexts + ["Create new context"],
#             ).ask()

#             if new_or_existing == "Create new context":
#                 context_name = questionary.text("Enter the new context name (this is your index name)").ask()
#                 if not context_name.strip():
#                     print("Invalid context name, returning to menu.")
#                     continue
#                 # add an empty entry in contexts
#                 contexts[context_name] = []
#             else:
#                 context_name = new_or_existing

#             # 4) For each selected repo, fetch+extract
#             for choice in to_embed:
#                 repo_obj = repo_choices[choice]
#                 # e.g. cisco-sbg/some-repo
#                 full_name = repo_obj["full_name"]
#                 if full_name not in contexts[context_name]:
#                     fetch_and_extract_repo(full_name, context_name)
#                     # add to contexts dictionary
#                     contexts[context_name].append(full_name)
#                 else:
#                     print(f"Repo {full_name} is already in context '{context_name}', skipping download.")
            
#             # 5) after extraction, embed everything that is in that context
#             # We simply embed the entire Repos/<context_name> folder
#             # because it might have multiple repos now
#             confirm_embed = questionary.confirm(
#                 f"Do you want to run multi-GPU embedding for context '{context_name}' now?"
#             ).ask()
#             if confirm_embed:
#                 base_path = Path("Repos") / context_name
#                 # Our multiprocess_embed logic from multi_gpu_embed
#                 multiprocess_embed(str(base_path), context_name)
            
#             # 6) save updated contexts
#             save_contexts(contexts)
#             print("Contexts updated & saved. Returning to main menu...")

#         elif action == "Exit":
#             print("Goodbye.")
#             break

# if __name__ == "__main__":
#     main()
# # cli.py

# # import os
# # import json
# # import questionary
# # import requests

# # from embeddings import embed  # or if you prefer: from embed import multiprocess_embed, load_and_chunk
# # from pathlib import Path

# # CONTEXTS_JSON = "contexts.json"
# # GITHUB_API_URL = "https://api.github.com"
# # ORGANIZATION = "cisco-sbg"

# # def load_contexts():
# #     if os.path.exists(CONTEXTS_JSON):
# #         with open(CONTEXTS_JSON, "r", encoding="utf-8") as f:
# #             return json.load(f)
# #     return {}

# # def save_contexts(contexts):
# #     with open(CONTEXTS_JSON, "w", encoding="utf-8") as f:
# #         json.dump(contexts, f, ensure_ascii=False, indent=2)

# # def get_github_token():
# #     token = os.getenv("GITHUB_TOKEN")
# #     if not token:
# #         raise ValueError("Please set GITHUB_TOKEN env var.")
# #     return token

# # def get_headers():
# #     return {
# #         "Authorization": f"token {get_github_token()}",
# #         "Accept": "application/vnd.github.v3+json",
# #     }

# # def search_repos_page(query, per_page=20, page=1):
# #     url = f"{GITHUB_API_URL}/search/repositories"
# #     headers = get_headers()
# #     params = {
# #         "q": f"{query} org:{ORGANIZATION}",
# #         "per_page": str(per_page),
# #         "page": str(page),
# #     }
# #     r = requests.get(url, headers=headers, params=params)
# #     if r.status_code == 200:
# #         data = r.json()
# #         items = data.get("items", [])
# #         total_count = data.get("total_count", 0)
# #         return items, total_count
# #     else:
# #         print(f"Error searching: {r.status_code} {r.reason}")
# #         return [], 0

# # def main():
# #     contexts = load_contexts()

# #     while True:
# #         action = questionary.select(
# #             "Main Menu: Choose an action",
# #             choices=[
# #                 "View contexts",
# #                 "Create/Update context with new repos",
# #                 "Exit",
# #             ],
# #         ).ask()

# #         if action == "View contexts":
# #             if not contexts:
# #                 print("No contexts yet.")
# #             else:
# #                 for ctx_name, repos in contexts.items():
# #                     print(f"\nContext: {ctx_name}")
# #                     for r in repos:
# #                         print(f"  - {r}")
# #         elif action == "Create/Update context with new repos":
# #             query = questionary.text("Enter a search term (e.g. 'sfcn'):").ask()

# #             page = 1
# #             total_selected = []
# #             while True:
# #                 batch, total_count = search_repos_page(query, per_page=20, page=page)
# #                 if not batch:
# #                     print("No repos or error. Stopping.")
# #                     break
# #                 # Show the user these 20 in a checkbox
# #                 label_to_repo = {}
# #                 for r in batch:
# #                     label = f"{r['full_name']} (★{r.get('stargazers_count',0)})"
# #                     label_to_repo[label] = r
# #                 selected = questionary.checkbox(
# #                     f"Select from these repos (page {page}/{total_count}):",
# #                     choices=list(label_to_repo.keys())
# #                 ).ask()
# #                 # Convert selections to actual repo objects
# #                 for lab in selected:
# #                     total_selected.append(label_to_repo[lab])
                
# #                 # If we haven't displayed all yet, ask if they want next 20
# #                 # e.g. if page * 20 < total_count => we can keep going
# #                 if page*20 < total_count:
# #                     see_more = questionary.confirm(
# #                         f"You've selected {len(total_selected)} so far. Show next 20?"
# #                     ).ask()
# #                     if see_more:
# #                         page += 1
# #                         continue
# #                 # Otherwise break
# #                 break

# #             if not total_selected:
# #                 print("No repos selected overall.")
# #                 continue

# #             # Now we have a list of selected repos from chunk-by-chunk selection
# #             # Ask user for context
# #             existing = list(contexts.keys())
# #             new_or_existing = questionary.select(
# #                 "Pick or create a context name",
# #                 choices=existing + ["Create new context"],
# #             ).ask()

# #             if new_or_existing == "Create new context":
# #                 context_name = questionary.text("Enter context/index name:").ask()
# #                 if not context_name.strip():
# #                     print("Invalid name.")
# #                     continue
# #             else:
# #                 context_name = new_or_existing

# #             # The user presumably has local directories in repos/<context_name>/<repo-name>
# #             # So we won't be "fetching" them from GitHub, we assume they're present.
# #             # If we do need to fetch them, we'd do that here. But you said "directories are copied already."
# #             # Next step: embed them

# #             # For each selected repo, we see if it's "cisco-sbg/<repo>" => local path: repos/<context_name>/<repo>
# #             # We'll ask "Embed them now?"
# #             confirm_embed = questionary.confirm(
# #                 f"Embed {len(total_selected)} selected repos into context '{context_name}'?"
# #             ).ask()
# #             if not confirm_embed:
# #                 print("Skipping embed.")
# #                 continue

# #             # We'll call embed_team(...) for each selected repo or once for the entire context?
# #             # If each repo is in repos/<context_name>/<repo_name>
# #             # we might just embed the entire directory repos/<context_name>.
# #             # We'll show how to do the entire directory.
# #             from embeddings import embed
# #             local_repo_dir = Path("repos") / context_name
# #             embed.embed_context(context_name, local_repo_dir)

# #             # after embedding, store them in contexts
# #             if context_name not in contexts:
# #                 contexts[context_name] = []
# #             for r in total_selected:
# #                 full_name = r["full_name"]
# #                 if full_name not in contexts[context_name]:
# #                     contexts[context_name].append(full_name)
# #             save_contexts(contexts)
# #             print(f"Context '{context_name}' updated with {len(total_selected)} new repos.")

# #         elif action == "Exit":
# #             print("Goodbye.")
# #             break

# # if __name__ == "__main__":
# #     main()
# # file: cli.py
# # import os
# # import json
# # import questionary
# # import requests
# # from pathlib import Path
# # import shutil
# # from io import BytesIO
# # import zipfile

# # # Our multi-GPU embedding logic
# # from embeddings import embed  # embed.py

# # GITHUB_API_URL = "https://api.github.com"
# # ORGANIZATION = "cisco-sbg"
# # CONTEXTS_JSON = "contexts.json"

# # def load_contexts():
# #     if os.path.exists(CONTEXTS_JSON):
# #         with open(CONTEXTS_JSON, "r", encoding="utf-8") as f:
# #             return json.load(f)
# #     return {}

# # def save_contexts(ctx_dict):
# #     with open(CONTEXTS_JSON, "w", encoding="utf-8") as f:
# #         json.dump(ctx_dict, f, ensure_ascii=False, indent=2)

# # def get_github_token():
# #     token = os.getenv("GITHUB_TOKEN")
# #     if not token:
# #         raise ValueError("GITHUB_TOKEN not set.")
# #     return token

# # def get_headers():
# #     return {
# #         "Authorization": f"token {get_github_token()}",
# #         "Accept": "application/vnd.github.v3+json"
# #     }

# # def search_repos_page(query, per_page=20, page=1):
# #     headers = get_headers()
# #     url = f"{GITHUB_API_URL}/search/repositories"
# #     params = {
# #         "q": f"{query} org:{ORGANIZATION}",
# #         "per_page": str(per_page),
# #         "page": str(page),
# #     }
# #     r = requests.get(url, headers=headers, params=params)
# #     if r.status_code == 200:
# #         data = r.json()
# #         items = data.get("items", [])
# #         total_count = data.get("total_count", 0)
# #         return items, total_count
# #     else:
# #         print(f"Error searching repos: {r.status_code} - {r.reason}")
# #         return [], 0

# # def fetch_repo_zip(repo_full_name, context_name):
# #     """
# #     Download the ZIP for 'cisco-sbg/repoName' => store in tmp/<context_name>/<repoName>.
# #     No random suffix. We remove it after embedding.
# #     """
# #     token = get_github_token()
# #     headers = get_headers()
# #     zip_url = f"{GITHUB_API_URL}/repos/{repo_full_name}/zipball"
# #     print(f"Fetching ZIP from: {zip_url}")

# #     resp = requests.get(zip_url, headers=headers, stream=True)
# #     if resp.status_code == 200:
# #         base_dir = Path("tmp") / context_name
# #         repo_name = repo_full_name.split("/", 1)[1]
# #         repo_path = base_dir / repo_name

# #         repo_path.mkdir(parents=True, exist_ok=True)

# #         zip_data = BytesIO(resp.content)
# #         with zipfile.ZipFile(zip_data, 'r') as zf:
# #             zf.extractall(repo_path)

# #         print(f"Extracted {repo_full_name} to {repo_path}")
# #         return True
# #     else:
# #         print(f"Failed to fetch {repo_full_name}: {resp.status_code} {resp.reason}")
# #         return False

# # def main():
# #     contexts = load_contexts()

# #     while True:
# #         action = questionary.select(
# #             "Main Menu",
# #             choices=[
# #                 "View existing contexts",
# #                 "Create/update context with new repos",
# #                 "Exit"
# #             ]
# #         ).ask()

# #         if action == "View existing contexts":
# #             if not contexts:
# #                 print("No contexts exist yet.")
# #             else:
# #                 for ctx, repos in contexts.items():
# #                     print(f"\nContext: {ctx}")
# #                     for r in repos:
# #                         print(f"  - {r}")
# #         elif action == "Create/update context with new repos":
# #             query = questionary.text("Enter a search term (e.g. 'sfcn')?").ask()

# #             page = 1
# #             total_selected = []
# #             while True:
# #                 batch, total_count = search_repos_page(query, per_page=20, page=page)
# #                 if not batch:
# #                     print("No repos found or error. Stopping.")
# #                     break

# #                 label_map = {}
# #                 for r in batch:
# #                     label = f"{r['full_name']} (★{r.get('stargazers_count',0)})"
# #                     label_map[label] = r

# #                 # Let user pick from this batch
# #                 chosen = questionary.checkbox(
# #                     f"Select from these repos (page {page}/{total_count})",
# #                     choices=list(label_map.keys())
# #                 ).ask()

# #                 for c in chosen:
# #                     total_selected.append(label_map[c])

# #                 # if we haven't displayed all results, ask "see next 20?"
# #                 if page * 20 < total_count:
# #                     see_more = questionary.confirm(f"You have selected {len(total_selected)}. Show next 20?").ask()
# #                     if see_more:
# #                         page += 1
# #                         continue
# #                 break

# #             if not total_selected:
# #                 print("No repos selected in total.")
# #                 continue

# #             # ask user for context name
# #             existing = list(contexts.keys())
# #             new_or_existing = questionary.select(
# #                 "Pick or create a context name",
# #                 choices=existing + ["Create new context"]
# #             ).ask()

# #             if new_or_existing == "Create new context":
# #                 context_name = questionary.text("Enter context/index name:").ask()
# #                 if not context_name.strip():
# #                     print("Invalid name.")
# #                     continue
# #             else:
# #                 context_name = new_or_existing

# #             # Let them confirm embedding
# #             confirm_embed = questionary.confirm(
# #                 f"Embed {len(total_selected)} repos into context '{context_name}'?"
# #             ).ask()
# #             if not confirm_embed:
# #                 print("Skipping embed.")
# #                 continue

# #             # Download each repo into tmp/<context_name>
# #             base_dir = Path("tmp") / context_name
# #             if base_dir.exists():
# #                 shutil.rmtree(base_dir)
# #             base_dir.mkdir(parents=True, exist_ok=True)

# #             good_downloads = []
# #             for r in total_selected:
# #                 # e.g. cisco-sbg/sfcn-xyz
# #                 full_name = r["full_name"]
# #                 success = fetch_repo_zip(full_name, context_name)
# #                 if success:
# #                     good_downloads.append(full_name)

# #             if not good_downloads:
# #                 print("No successful downloads. Skipping embed.")
# #                 # remove folder
# #                 shutil.rmtree(base_dir, ignore_errors=True)
# #                 continue

# #             # Now call embed_context
# #             from embeddings.embed import embed_context
# #             embed_context(context_name, str(base_dir))

# #             # after embedding, remove the entire tmp/<context_name> folder
# #             shutil.rmtree(base_dir, ignore_errors=True)
# #             print(f"Removed local code folder for context '{context_name}'")

# #             # add them to contexts
# #             if context_name not in contexts:
# #                 contexts[context_name] = []
# #             for f in good_downloads:
# #                 if f not in contexts[context_name]:
# #                     contexts[context_name].append(f)
# #             save_contexts(contexts)
# #             print(f"Context '{context_name}' updated with {len(good_downloads)} repos.")

# #         elif action == "Exit":
# #             print("Bye.")
# #             break

# # if __name__ == "__main__":
# #     main()
import os
import json
import questionary
import requests
from io import BytesIO
import zipfile
from pathlib import Path

from embeddings.embed import embed_context  # The function we wrote in embed.py

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
        repo_name = repo_full_name.split("/",1)[1]
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

def main():
    contexts = load_contexts()

    while True:
        action = questionary.select(
            "Main Menu: Choose an action",
            choices=[
                "View existing contexts",
                "Create / update context with new repos",
                "Exit",
            ],
        ).ask()

        if action == "View existing contexts":
            if not contexts:
                print("No contexts exist.")
            else:
                for ctx, repos in contexts.items():
                    print(f"\nContext: {ctx}")
                    for r in repos:
                        print(f"  - {r}")

        elif action == "Create / update context with new repos":
            query = questionary.text("Search term (e.g. 'sfcn')?").ask()
            results = search_repos(ORGANIZATION, query)
            if not results:
                print("No repos found.")
                continue

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
                continue

            existing_names = list(contexts.keys())
            new_or_existing = questionary.select(
                "Pick or create a context name:",
                choices=existing_names + ["Create new context"]
            ).ask()

            if new_or_existing == "Create new context":
                context_name = questionary.text("Enter context name (index)").ask()
                if not context_name.strip():
                    print("Invalid context name.")
                    continue
            else:
                context_name = new_or_existing

            # Ask if user wants to embed now
            confirm_embed = questionary.confirm(
                f"Embed {len(selected_labels)} repos into context '{context_name}' now?"
            ).ask()
            if not confirm_embed:
                print("Skipping embed.")
                continue

            # For each selected repo:
            # 1) Download if not already in contexts
            # 2) embed_context(context_name, that path)
            newly_embedded = []
            for lbl in selected_labels:
                r = label_map[lbl]
                full_name = r["full_name"]
                # if we've already embedded this repo in that context, skip
                already_in_context = context_name in contexts and (full_name in contexts[context_name])
                if already_in_context:
                    print(f"Repo {full_name} is already in context {context_name}, skipping download.")
                    continue

                # fetch repo zip => repos/<context_name>/<repo_name>
                extracted_path = fetch_repo_zip(full_name, context_name)
                if not extracted_path:
                    print("Download failed, skipping embed.")
                    continue

                # embed
                from embeddings.embed import embed_context
                embed_context(context_name, str(extracted_path))

                # add to contexts
                if context_name not in contexts:
                    contexts[context_name] = []
                contexts[context_name].append(full_name)
                newly_embedded.append(full_name)

            # save contexts
            if newly_embedded:
                save_contexts(contexts)
                print(f"Embedded {len(newly_embedded)} repos in context '{context_name}'. Updated contexts saved.")

        elif action == "Exit":
            print("Goodbye.")
            break

if __name__ == "__main__":
    main()
