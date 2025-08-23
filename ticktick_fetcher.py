import os
import json
import logging
from requests_ratelimiter import LimiterSession

class TickTickClient:
    """
    A client for the TickTick API that uses a rate-limited session.
    """
    BASE_URL = "https://api.ticktick.com/open/v1"

    def __init__(self, api_key):
        if not api_key:
            raise ValueError("API key cannot be empty.")
        self.api_key = api_key
        
        # Create a rate-limited session
        # 60 requests per 60 seconds (1 minute)
        # The library also handles burst requests, we can set a per_second limit
        self.session = LimiterSession(per_minute=60, per_second=3)
        self.session.headers.update({"Authorization": f"Bearer {self.api_key}"})

    def _request(self, method, endpoint, **kwargs):
        """
        Makes a request to the TickTick API using the rate-limited session.
        """
        url = f"{self.BASE_URL}/{endpoint}"
        response = self.session.request(method, url, **kwargs)
        response.raise_for_status()
        return response.json()

    def get_projects(self) -> dict:
        """
        Fetches all projects.
        """
        return self._request("GET", "project")

    def get_tasks_for_project(self, project_id):
        """
        Fetches all tasks for a given project.
        """
        return self._request("GET", f"project/{project_id}/data")

    def get_all_data(self):
        """
        Fetches all projects and their associated tasks.
        """
        projects = self.get_projects()
        filtered_projects = [item for item in projects if not item.get("closed")]
        tasks = []
        for index, project in enumerate(filtered_projects):
            if not project.get("closed"):
                logging.info(f"Fetching tasks for project: {index} out of {len(filtered_projects) -1}")
                project_data = self.get_tasks_for_project(project['id'])
                tasks.extend(project_data.get('tasks', []))
                # if index == 5:
                #     break
        task_keys_to_drop = {"desc", "content", "items"}
        slim_tasks = [
            {key: value for key, value in item.items() if key not in task_keys_to_drop}
            for item in tasks
        ]
        return filtered_projects, slim_tasks

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    api_key = os.getenv("TICKTICK_API_KEY")
    if not api_key:
        raise Exception("Error: Please set the TICKTICK_API_KEY environment variable.")
    else:
        client = TickTickClient(api_key)
        projects, tasks = client.get_all_data()
        
        # Save to a file
        with open("tasks_raw.json", "w") as f:
            json.dump(tasks, f, indent=2)
        with open("projects_raw.json", "w") as f:
            json.dump(projects, f, indent=2)
            
        logging.info("Data fetching complete")
