import os
import json
import logging
from requests_ratelimiter import LimiterSession
from typing import List, Dict
from dotenv import load_dotenv
from pathlib import Path; root_dir = (Path(__file__).parent / '..' / '..').resolve()
env_path = root_dir / ".env"

load_dotenv(env_path)
class TodoistClient:
    """
    A client for the Todoist API that uses a rate-limited session
    and handles pagination.
    """
    BASE_URL = "https://api.todoist.com/api/v1"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key
        
        # Create a rate-limited session
        # The Todoist Sync API has a limit of 450 requests per 15 minutes.
        # We'll be more conservative to be safe.
        self.session = LimiterSession(per_minute=60)
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _request(self, method: str, endpoint: str, **kwargs) -> Dict:
        """
        Makes a request to the Todoist API using the rate-limited session.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logging.error(f"API request to {url} failed: {e}")
            raise

    def _paginated_request(self, endpoint: str, resource_name: str, params: Dict = {}) -> List[Dict]:
        """
        Handles cursor-based pagination for a given endpoint.
        """
        logging.info(f"Fetching all {resource_name}...")
        items = []
        next_cursor = None
        page_num = 1
        
        if params is None:
            params = {}
        
        params.setdefault("limit", 200)

        while True:
            if next_cursor:
                params["cursor"] = next_cursor

            logging.info(f"Fetching page {page_num} of {resource_name}...")
            response_data = self._request("GET", endpoint, params=params)
            
            new_items = response_data.get("results", [])
            items.extend(new_items)
            
            next_cursor = response_data.get("next_cursor")
            
            if not next_cursor:
                break
            page_num += 1

        logging.info(f"Successfully fetched a total of {len(items)} {resource_name}.")
        return items

    def get_active_projects(self) -> List[Dict]:
        """
        Fetches all active projects.
        """
        logging.info("Fetching all projects...")
        projects = self._request("GET", "projects")['results']
        logging.info(f"Successfully fetched {len(projects)} projects.")
        # TODO: handle bq load this struct cause it'll crash the
        # external table if we included empty config: {} struct.
        projects = [
            {k:v for k, v in project.items() if k != 'access'}
            for project in projects
        ]
        return projects

    def get_archived_projects(self) -> List[Dict]:
        """
        Fetches archived projects.
        """
        projects = self._paginated_request("projects/archived", "archived projects")
        # TODO: handle bq load this struct cause it'll crash the
        # external table if we included empty config: {} struct.
        projects = [
            {k:v for k, v in project.items() if k != 'access'}
            for project in projects
        ]
        return projects

    def get_active_tasks(self) -> List[Dict]:
        """
        Fetches all active tasks using cursor-based pagination.
        """
        return self._paginated_request("tasks", "active tasks")
        
    def get_completed_tasks(self) -> List[Dict]:
        """
        Fetches all completed tasks using offset-based pagination.
        """
        logging.info("Fetching all completed tasks...")
        all_tasks = []
        offset = 0
        limit = 200  # Max limit for completed tasks is 200
        page_num = 1

        while True:
            params = {"limit": limit, "offset": offset}
            
            logging.info(f"Fetching page {page_num} of completed tasks...")
            response_data = self._request("GET", "tasks/completed", params=params)
            
            tasks = response_data.get("items", [])
            if not tasks:
                break  # Stop if no more tasks are returned
            
            all_tasks.extend(tasks)
            
            offset += limit
            page_num += 1
            
        logging.info(f"Successfully fetched a total of {len(all_tasks)} completed tasks.")
        return all_tasks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    api_key = os.getenv("TODOIST_API_KEY")
    
    if not api_key:
        raise Exception("Error: Please set the TODOIST_API_KEY environment variable.")
    
    client = TodoistClient(api_key)
    
    # Fetch all data
    active_projects = client.get_active_projects()
    archived_projects = client.get_archived_projects()
    active_tasks = client.get_active_tasks()
    completed_tasks = client.get_completed_tasks()

    logging.info("dumping files...")
    datasets = {
        "active_projects.jsonl": active_projects,
        "archived_projects.jsonl": archived_projects,
        "active_tasks.jsonl": active_tasks,
        "completed_tasks.jsonl": completed_tasks,
    }
    raw_dir = Path(__file__).parent / "raw"
    

    for filename, data in datasets.items():
        jsonl_content = "\n".join([json.dumps(record, ensure_ascii=False) for record in data])
        (raw_dir / filename).write_text(
            jsonl_content,
            encoding="utf-8"
        )
    logging.info("Data fetching complete.")
