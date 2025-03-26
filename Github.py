import requests
import os
import questionary
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import time
import random
from urllib.parse import urljoin
import zipfile
from io import BytesIO
# from rag import search_opensearch
from embeddings import create_embeddings

GITHUB_API_URL = "https://api.github.com"
ORGANIZATION = "cisco-sbg"


def fetch_and_extract_repo(repo_url, team_name, repo_name):
    headers = get_headers()
    zip_url = f"{repo_url}/zipball"
    print(zip_url)
    response = requests.get(zip_url, headers=headers)

    if response.status_code == 200:
        zip_data = BytesIO(response.content)
        with zipfile.ZipFile(zip_data, 'r') as zip_ref:
            extract_path = os.path.join("Repos", team_name, repo_name)
            os.makedirs(extract_path, exist_ok=True)
            zip_ref.extractall(extract_path)
        print(f"Repository {repo_name} extracted to {extract_path}")
    else:
        print(f"Failed to fetch repository: {response.status_code} - {response.reason}")

def get_headers():
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GitHub token not found. Please set the GITHUB_TOKEN environment variable.")
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

@lru_cache(maxsize=None)
def get_teams(organization):
    headers = get_headers()
    url = f'{GITHUB_API_URL}/orgs/{organization}/teams'
    return get_paginated_results(url, headers)

# def get_paginated_results(url, headers):
#     results = []
#     urls = [url]
#
#     with ThreadPoolExecutor(max_workers=10) as executor:
#         while urls:
#             future_to_url = {executor.submit(requests.get, url, headers=headers): url for url in urls}
#             urls = []
#             for future in as_completed(future_to_url):
#                 response = future.result()
#                 if response.status_code == 200:
#                     results.extend(response.json())
#                     if 'Link' in response.headers:
#                         links = response.headers['Link'].split(',')
#                         for link in links:
#                             if 'rel="next"' in link:
#                                 next_url = link[link.find('<') + 1:link.find('>')]
#                                 urls.append(next_url)
#                 else:
#                     print(f"Error: {response.status_code} - {response.reason}")
#                     break
#     return results

def get_paginated_results(
    url,
    headers,
    max_workers=20,
    max_retries=3,
    retry_delay=1,
    max_pages=None,
):
    """
    Optimized version to fetch paginated results with reduced execution time.

    Args:
    - url (str): Initial URL to query.
    - headers (dict): Request headers.
    - max_workers (int): Number of parallel threads. Default is 20.
    - max_retries (int): Max retries for failed requests. Default is 3.
    - retry_delay (int): Initial retry delay in seconds. Default is 1.
    - max_pages (int or None): Maximum number of pages to fetch (optional).

    Returns:
    - list: Combined results from all pages.
    """

    results = []
    urls = [url]
    visited_urls = set()
    page_count = 0

    def fetch_url(url):
        """Fetch a single URL with retries and adaptive backoff."""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=5)
                if response.status_code == 200:
                    return response
                else:
                    print(
                        f"⚠️ Warning: {response.status_code} - {response.reason} (URL: {url})"
                    )
            except requests.RequestException as e:
                print(f"⚠️ Request failed: {e} (Attempt {attempt + 1}/{max_retries})")

            # Exponential backoff with jitter
            backoff_time = retry_delay * (2**attempt) + random.uniform(0, 1)
            time.sleep(backoff_time)
        print(f"❌ Failed after {max_retries} attempts. Skipping: {url}")
        return None

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        while urls and (max_pages is None or page_count < max_pages):
            future_to_url = {
                executor.submit(fetch_url, url): url for url in urls
            }
            urls = []
            for future in as_completed(future_to_url):
                response = future.result()
                if response:
                    try:
                        data = response.json()
                        if isinstance(data, list):
                            results.extend(data)
                        elif isinstance(data, dict):
                            results.append(data)

                        # Handle pagination via 'Link' header
                        if "Link" in response.headers:
                            links = response.headers["Link"].split(",")
                            for link in links:
                                if 'rel="next"' in link:
                                    next_url = link[link.find("<") + 1 : link.find(">")]
                                    next_url = urljoin(response.url, next_url)
                                    if next_url not in visited_urls:
                                        visited_urls.add(next_url)
                                        urls.append(next_url)

                    except ValueError:
                        print(
                            f"⚠️ Invalid JSON in response from {future_to_url[future]}"
                        )
                page_count += 1

    return results

@lru_cache(maxsize=None)
def get_team_repos(organization, team_slug):
    headers = get_headers()
    url = f'{GITHUB_API_URL}/orgs/{organization}/teams/{team_slug}/repos'
    return get_paginated_results(url, headers)

def search_repos(organization, query):
    headers = get_headers()
    response = requests.get(f'{GITHUB_API_URL}/search/repositories?q={query}+org:{organization}', headers=headers)
    if response.status_code == 200:
        results = response.json()
        for repo in results.get('items', []):
            print(f"Repository: {repo['name']} - {repo['html_url']}")
        return results.get('items', [])

    else:
        print(f"Error: {response.status_code} - {response.reason}")

# def main():
#     organization = questionary.text("Enter your GitHub Organization Name:").ask()
#
#     while True:
#         action = questionary.select(
#             "Choose an action:",
#             choices=[
#                 "List all teams in the organization",
#                 "List repositories for a specific team",
#                 "Search for repositories in the organization",
#                 "Exit"
#             ]
#         ).ask()
#         if action == "List all teams in the organization":
#             teams = get_teams(organization)
#             if teams:
#                 print("\nTeams:")
#                 for team in teams:
#                     print(f"- {team['name']} (Slug: {team['slug']})")
#             else:
#                 print("No teams found or an error occurred.")
#         elif action == "List repositories for a specific team":
#             teams = get_teams(organization)
#             if teams:
#                 team_choices = {team['name']: team['slug'] for team in teams}
#                 team_name = questionary.select("Select a team:", choices=team_choices.keys()).ask()
#                 team_slug = team_choices[team_name]
#                 repos = get_team_repos(organization, team_slug)
#                 if repos:
#                     print("\nSearch Results:")
#                     repo_choices = {repo['name']: {'repo': repo, 'team': team_name} for repo in repos}
#                     selected_repos = {repo_name: repo_choices[repo_name] for repo_name in questionary.checkbox("Select repositories:", choices=repo_choices.keys()).ask()}
#                     extracted_data = {}
#                     for repo_name in selected_repos:
#                         selected_repo = repo_choices[repo_name]['repo']
#                         extracted_data[repo_choices[repo_name]['repo']] = repo_choices
#                         print(
#                             f"Selected Repository: {selected_repo['name']} ({selected_repo['html_url']})")
#                     print(selected_repos)
#                     while True:
#                         prompt = questionary.text("Enter a prompt or type 'exit' to return to the main menu:").ask()
#                         if prompt.lower() == 'exit':
#                             break
#                 else:
#                     print(f"No repositories found for team {team_name} or an error occurred.")
#             else:
#                 print("No teams available to select.")
#         elif action == "Search for repositories in the organization":
#             query = questionary.text("Enter search query:").ask()
#             repos = search_repos(organization, query)
#             if repos:
#                 print("\nSearch Results:")
#                 repo_choices = {repo['name']: {'repo': repo, 'team': team_name} for repo in repos}
#                 selected_repos = questionary.checkbox("Select repositories:", choices=repo_choices.keys()).ask()
#                 for repo_name in selected_repos:
#                     selected_repo = repo_choices[repo_name]['repo']
#                     selected_team = repo_choices[repo_name]['team']
#                     print(
#                         f"Selected Repository: {selected_repo['name']} ({selected_repo['html_url']}) - Team: {selected_team}")
#                 print(selected_repos)
#                 while True:
#                     prompt = questionary.text("Enter a prompt or type 'exit' to return to the main menu:").ask()
#                     if prompt.lower() == 'exit':
#                         break
#                     # else:
#                     #     rag.search_opensearch(prompt)
#             else:
#                 print("No repositories found matching the query or an error occurred.")
#         elif action == "Exit":
#             print("Exiting the application.")
#             break
#         else:
#             print("Invalid selection. Please choose a valid action.")


def search_repos(organization, query):
    headers = get_headers()
    response = requests.get(f'{GITHUB_API_URL}/search/repositories?q={query}+org:{organization}', headers=headers)
    if response.status_code == 200:
        results = response.json()
        for repo in results.get('items', []):
            print(f"Repository: {repo['name']} - {repo['html_url']}")
        return results.get('items', [])
    else:
        print(f"Error: {response.status_code} - {response.reason}")

def main():
    organization = questionary.text("Enter your GitHub Organization Name:").ask()

    while True:
        action = questionary.select(
            "Choose an action:",
            choices=[
                "List all teams in the organization",
                "List repositories for a specific team",
                "Search for repositories in the organization",
                "Exit"
            ]
        ).ask()
        if action == "List all teams in the organization":
            teams = get_teams(organization)
            if teams:
                print("\nTeams:")
                for team in teams:
                    print(f"- {team['name']} (Slug: {team['slug']})")
            else:
                print("No teams found or an error occurred.")
        elif action == "List repositories for a specific team":
            teams = get_teams(organization)
            if teams:
                team_choices = {team['name']: team['slug'] for team in teams}
                team_name = questionary.select("Select a team:", choices=team_choices.keys()).ask()
                team_slug = team_choices[team_name]
                repos = get_team_repos(organization, team_slug)
                if repos:
                    print("\nSearch Results:")
                    repo_choices = {repo['name']: {'repo': repo, 'team': team_name} for repo in repos}
                    selected_repos = {repo_name: repo_choices[repo_name] for repo_name in questionary.checkbox("Select repositories:", choices=repo_choices.keys()).ask()}
                    for repo_name in selected_repos:
                        selected_repo = repo_choices[repo_name]['repo']
                        print(
                            f"Selected Repository: {selected_repo['name']} ({selected_repo['html_url']})")
                    print(selected_repos)
                    extracted_data = {}
                    for repo_key, repo_data in selected_repos.items():
                        extracted_data[repo_data["repo"]["name"]] = repo_data["team"]
                    print(extracted_data)
                    for repo_name, team_name in extracted_data.items():
                        repo_url = f"{GITHUB_API_URL}/{ORGANIZATION}/{repo_name}"
                        fetch_and_extract_repo(repo_url, team_name, repo_name)
                    while True:
                        prompt = questionary.text("Enter a prompt or type 'exit' to return to the main menu:").ask()
                        if prompt.lower() == 'exit':
                            break
                else:
                    print(f"No repositories found for team {team_name} or an error occurred.")
            else:
                print("No teams available to select.")
        elif action == "Search for repositories in the organization":
            query = questionary.text("Enter search query:").ask()
            repos = search_repos(organization, query)
            if repos:
                print("\nSearch Results:")
                repo_choices = {repo['name']: {'repo': repo} for repo in repos}
                selected_repos = questionary.checkbox("Select repositories:", choices=repo_choices.keys()).ask()
                for repo_name in selected_repos:
                    selected_repo = repo_choices[repo_name]['repo']
                    print(
                        f"Selected Repository: {selected_repo['name']} ({selected_repo['html_url']})")
                print(selected_repos)
                extracted_data = {}
                for repo_key, repo_data in selected_repos.items():
                    extracted_data[repo_data["repo"]["name"] ] = repo_data["team"]
                print(extracted_data)
                #fetch the repos
                while True:
                    prompt = questionary.text("Enter a prompt or type 'exit' to return to the main menu:").ask()
                    if prompt.lower() == 'exit':
                        break
            else:
                print("No repositories found matching the query or an error occurred.")
        elif action == "Exit":
            print("Exiting the application.")
            break
        else:
            print("Invalid selection. Please choose a valid action.")


if __name__ == '__main__':
    import pdb
    pdb.set_trace()
    main()

