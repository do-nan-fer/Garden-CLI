import click
import requests
import tempfile
import os
import yaml
from tabulate import tabulate
from datetime import datetime, timezone
from functools import reduce
import operator

API_BASE_URL = 'http://192.168.101.5:8500'  # Adjust the base URL as needed

@click.group()
def cli():
    """Garden CLI tool."""
    pass

@cli.command('list-plants')
@click.argument('plant_id', type=int, required=False)
def list_plants(plant_id=None):
    """List all plants or a single plant by ID."""
    url = f'{API_BASE_URL}/plants/{plant_id}/' if plant_id else f'{API_BASE_URL}/plants/'
    response = requests.get(url)
    data = response.json()

    plants = [data] if plant_id else data

    table = []
    for plant in plants:
        # Determine the status display based on conditions
        if plant['status'] == 'DOWN':
            status = click.style(plant['status'], fg='red')
        elif plant['status'] == 'STOP':
            status = click.style(plant['status'], fg='yellow')
        elif plant['status'] == 'ONLINE':
            status = click.style(plant['status'], fg='cyan')

        # Use the provided 'since' value from the API
        since_str = plant['since']

        table.append([plant['id'], plant['name'], plant['number_of_packages'], plant['number_of_fields'], status, since_str])

    headers = ['ID', 'NAME', 'WORKERS', 'FIELDS', 'STATUS', 'SINCE']
    click.echo(tabulate(table, headers=headers, tablefmt='plain'))

@cli.command('add-plant')
def add_plant():
    """Add a new plant by asking for details and using the default text editor."""
    # Ask for plant name and description
    plant_name = click.prompt("Please enter the plant's name")
    plant_description = click.prompt("Please enter the plant's description")

    # Open an empty temporary file in the default text editor for the command
    with tempfile.NamedTemporaryFile(suffix=".txt", mode='w+', delete=False) as tf:
        tf_path = tf.name

    click.echo("Opening the default text editor for you to add the plant command...")
    editor = os.environ.get('EDITOR', 'vim')  # Use EDITOR env variable or default to vim
    os.system(f'{editor} "{tf_path}"')  # Open the editor to edit the command

    # Read the command from the updated file
    with open(tf_path, 'r') as tf:
        plant_command = tf.read().strip()
        print("comando:", plant_command)

    os.unlink(tf_path)  # Clean up the temporary file

    # Combine details into plant data
    new_plant_data = {
        "name": plant_name,
        "description": plant_description,
        "full_query_command": plant_command
    }

    # Check if any field is left blank
    if not all(new_plant_data.values()):
        click.echo("Some fields are left blank. Please fill in all fields. Operation cancelled.")
        return

    # Send a POST request to the API to add the new plant
    url = f'{API_BASE_URL}/plants/add/'
    response = requests.post(url, json=new_plant_data)

    if response.status_code in [200, 201]:
        click.echo(f"Plant '{new_plant_data.get('name')}' added successfully.")
    else:
        click.echo(f"Failed to add plant. Status code: {response.status_code}, Response: {response.text}")

@cli.command('edit-plant')
@click.argument('plant_id', type=int)
def edit_plant(plant_id):
    """Edit details of a plant without changing its ID, collect status, plant status, guid, or active status."""
    url = f'{API_BASE_URL}/plants/{plant_id}/'
    response = requests.get(url)
    if response.status_code != 200:
        click.echo(f"Failed to fetch plant with ID {plant_id}. Status code: {response.status_code}, Response: {response.text}")
        return

    plant_data = response.json()

    # Prompt for new name and description, keep old if blank
    new_name = click.prompt("Enter new plant name or press Enter to keep the current one", default=plant_data['name'], show_default=False)
    new_description = click.prompt("Enter new plant description or press Enter to keep the current one", default=plant_data['description'], show_default=False)

    # Use a temporary file for command editing
    with tempfile.NamedTemporaryFile(suffix=".txt", mode='w+', delete=False) as tf:
        tf.write(plant_data['full_query_command'])  # Pre-fill with the current command
        tf.flush()  # Ensure all data is written to the file
        tf_path = tf.name

    click.echo("Opening the default text editor for you to edit the plant command. Leave as is to keep the current command.")
    editor = os.environ.get('EDITOR', 'vim')
    os.system(f'{editor} "{tf_path}"')

    # Read the potentially updated command
    with open(tf_path, 'r') as tf:
        updated_command = tf.read().strip()

    os.unlink(tf_path)  # Clean up the temporary file

    # Encode the command to ensure it's safely transmitted
    encoded_command = updated_command.encode('unicode_escape').decode('utf-8')

    updated_plant_data = {
        'name': new_name,
        'description': new_description,
        'full_query_command': encoded_command,  # Use the encoded command
    }

    headers = {'Content-Type': 'application/json'}

    # Use PATCH to update the plant, ensuring to include the content-type header
    update_response = requests.patch(url + 'update/', json=updated_plant_data, headers=headers)
    if update_response.status_code in [200, 204]:
        click.echo(f"Plant '{updated_plant_data.get('name')}' updated successfully.")
    else:
        click.echo(f"Failed to update plant. Status code: {update_response.status_code}, Response: {update_response.text}")

@cli.command('remove-plant')
@click.argument('plant_id', type=int)
def remove_plant(plant_id):
    """Remove a plant from the database."""
    url = f'{API_BASE_URL}/plants/{plant_id}/delete/'
    response = requests.delete(url)
    if response.status_code in [200, 204]:
        click.echo(f"Plant ID {plant_id} removed successfully.")
    else:
        click.echo(f"Failed to remove plant ID {plant_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('list-actions')
@click.argument('action_id', type=int, required=False)
def list_actions(action_id=None):
    """List all actions or a single action by ID."""
    url = f'{API_BASE_URL}/actions/{action_id}/' if action_id else f'{API_BASE_URL}/actions/'
    response = requests.get(url)
    data = response.json()

    actions = [data] if action_id else data

    table = []
    for action in actions:
        params_count = len(action['params'])  # Get the count of parameters
        status_display = 'ON' if action['status'] == 1 else 'OFF'  # Convert status to human-readable form

        table.append([
            action['id'],
            action['group'],
            action['name'],
            params_count,  # Display the count of params here
            status_display,
            action['last_status_change']
        ])

    headers = ['ID', 'GROUP', 'NAME', 'PARAMS', 'STATUS', 'SINCE']  # Add 'PARAMS' to headers
    click.echo(tabulate(table, headers=headers, tablefmt='plain'))

@cli.command('add-action')
def add_action():
    """Add a new action by asking for details and allowing for individual parameter entry."""
    action_group = click.prompt("Please enter the action's group")
    action_name = click.prompt("Please enter the action's name")
    action_description = click.prompt("Please enter the action's description")

    action_params = []
    param_index = 1
    while True:
        param = click.prompt(f"Enter Parameter N°{param_index} or press Enter to finish", default="", show_default=False)
        if param == "":
            break
        action_params.append(param)
        param_index += 1

    # Open an empty temporary file in the default text editor for the action code
    with tempfile.NamedTemporaryFile(suffix=".py", mode='w+', delete=False) as tf:
        tf_path = tf.name

    click.echo("Opening the default text editor for you to add the action code...")
    editor = os.environ.get('EDITOR', 'vim')
    os.system(f'{editor} "{tf_path}"')

    # Read the code from the updated file
    with open(tf_path, 'r') as tf:
        action_code = tf.read().strip()

    os.unlink(tf_path)  # Clean up the temporary file

    # Combine details into action data
    new_action_data = {
        "group": action_group,
        "name": action_name,
        "description": action_description,
        "params": action_params,
        "code": action_code
    }

    # Send a POST request to the API to add the new action
    url = f'{API_BASE_URL}/actions/'
    response = requests.post(url, json=new_action_data)

    if response.status_code in [200, 201]:
        click.echo(f"Action '{new_action_data.get('name')}' added successfully.")
    else:
        click.echo(f"Failed to add action. Status code: {response.status_code}, Response: {response.text}")

@cli.command('edit-action')
@click.argument('action_id', type=int)
def edit_action(action_id):
    """Edit an existing action's details including parameters and code."""
    # Fetch the existing action data
    url = f'{API_BASE_URL}/actions/{action_id}/'
    response = requests.get(url)
    if response.status_code != 200:
        click.echo(f"Failed to fetch action with ID {action_id}. Status code: {response.status_code}, Response: {response.text}")
        return

    action_data = response.json()

    # Prompt for new values or use existing ones
    new_group = click.prompt("Enter new action group or press Enter to keep the current one", default=action_data['group'], show_default=False)
    new_name = click.prompt("Enter new action name or press Enter to keep the current one", default=action_data['name'], show_default=False)
    new_description = click.prompt("Enter new action description or press Enter to keep the current one", default=action_data['description'], show_default=False)

    # Edit existing parameters and possibly add new ones
    new_params = []
    for i, old_param in enumerate(action_data['params'], start=1):
        new_param = click.prompt(f"Parameter N°{i} [{old_param}]: enter new param or press Enter to keep the current one", default=old_param, show_default=False)
        new_params.append(new_param)

    # Adding new parameters
    while True:
        new_param = click.prompt(f"Enter new parameter or press Enter if done (Parameter N°{len(new_params) + 1})", default="", show_default=False)
        if not new_param:
            break
        new_params.append(new_param)

    # Handling the action code
    with tempfile.NamedTemporaryFile(suffix=".py", mode='w+', delete=False) as tf:
        # Pre-fill the temp file with the existing action code
        tf.write(action_data['code'])
        tf.flush()
        tf_path = tf.name

    click.echo("Opening the default text editor for you to edit the action code. Leave as is to keep the current code.")
    editor = os.environ.get('EDITOR', 'vim')
    os.system(f'{editor} "{tf_path}"')

    with open(tf_path, 'r') as tf:
        updated_code = tf.read().strip()

    os.unlink(tf_path)  # Clean up the temporary file

    # Prepare the updated action data
    updated_action_data = {
        'group': new_group,
        'name': new_name,
        'description': new_description,
        'params': new_params,
        'code': updated_code,
    }

    # Send the update request to the API
    update_response = requests.patch(url, json=updated_action_data)
    if update_response.status_code in [200, 204]:
        click.echo(f"Action '{updated_action_data.get('name')}' updated successfully.")
    else:
        click.echo(f"Failed to update action. Status code: {update_response.status_code}, Response: {update_response.text}")

@cli.command('remove-action')
@click.argument('action_id', type=int)
def remove_action(action_id):
    """Remove an action."""
    url = f'{API_BASE_URL}/actions/{action_id}/'
    response = requests.delete(url)
    if response.status_code in [200, 204]:
        click.echo(f"Action ID {action_id} removed successfully.")
    else:
        click.echo(f"Failed to remove action ID {action_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('execute-action')
@click.argument('action_id', type=int)
def execute_action(action_id):
    """Execute an action by its ID with user-provided parameters."""
    # Fetch the action details to get the required parameters
    url = f'{API_BASE_URL}/actions/{action_id}/'
    response = requests.get(url)
    if response.status_code != 200:
        click.echo(f"Failed to fetch action with ID {action_id}. Status code: {response.status_code}, Response: {response.text}")
        return

    action_data = response.json()
    params = action_data['params']

    # Prompt for parameter values
    param_values = []
    for i, param in enumerate(params, start=1):
        value = click.prompt(f"Parameter N°{i} ({param})")
        param_values.append(value)

    # Construct the URL with parameters for the execution endpoint
    params_query = ",".join(param_values)
    execute_url = f'{API_BASE_URL}/actions/{action_id}/execute/?params={params_query}'

    # Execute the action by sending a GET request to the execute URL
    execute_response = requests.get(execute_url)
    if execute_response.status_code == 200:
        click.echo("Action executed successfully.")
        click.echo(execute_response.text)
    else:
        click.echo(f"Failed to execute action. Status code: {execute_response.status_code}, Response: {execute_response.text}")

@cli.command('watch-plant')
@click.argument('plant_id', type=int, required=True)
def watch_plant(plant_id):
    """Watch a specific plant by ID."""
    url = f'{API_BASE_URL}/plants/{plant_id}/'
    response = requests.get(url)

    if response.status_code == 200:
        plant_data = response.json()

        # Display plant information
        click.echo(f"- {plant_data['guid']}")
        click.echo(f"- {plant_data['name']}")
        click.echo(f"- {plant_data['description']}")
        click.echo(f"- {plant_data['status']}")
        click.echo()

        # Fetch plant data
        url = f'{API_BASE_URL}/plants/{plant_id}/data/'
        response = requests.get(url)

        if response.status_code == 200:
            data = response.json()

            table = []
            count = 1

            for key, value in data.items():
                parts = key.split('.')
                if parts[0] == 'response':
                    parts.pop(0)
                full_key = '.'.join(parts)

                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        full_sub_key = f"{full_key}.{sub_key}"
                        # Apply bright green color to the value
                        colored_value = click.style(str(sub_value), fg='bright_green')
                        table.append([count, full_sub_key, colored_value])
                        count += 1
                else:
                    # Apply bright green color to the value
                    colored_value = click.style(str(value), fg='bright_green')
                    table.append([count, full_key, colored_value])
                    count += 1

            # Print the table using tabulate without Click's echo, as echo might interfere with tabulate's formatting
            print(tabulate(table, headers=['', 'FIELD', 'VALUE'], tablefmt='plain'))
        else:
            # Handle errors with styled message
            click.echo(click.style(f'Failed to fetch data for plant ID {plant_id}. Response Code: {response.status_code}', fg='red'))
    else:
        # Handle errors with styled message
        click.echo(click.style(f'Failed to fetch plant information for plant ID {plant_id}. Response Code: {response.status_code}', fg='red'))

@cli.command('watch-package')
@click.argument('package_id', type=int, required=True)
def watch_package(package_id):
    """Watch a specific package by ID."""
    url = f'{API_BASE_URL}/package/{package_id}/'
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()

        # Display package information
        click.echo(f"- {data['package_guid']}")
        click.echo(f"- {data['package_name']}")
        click.echo(f"- {data['package_description']}")
        click.echo(f"- {data['package_status']}")
        click.echo()

        # Display table with pick data
        table = []
        count = 1
        for pick_id, pick_data in data['picks'].items():
            plant_id = pick_data['plant_id']
            for key, value in pick_data['data'].items():
                color = 'blue' if plant_id % 2 != 1 else None
                table.append([count, click.style(str(plant_id), fg=color), key, click.style(str(value), fg='bright_green')])
                count += 1

        # Print the table with aligned fields
        click.echo(tabulate(table, headers=['', 'PLANT', 'FIELD', 'VALUE'], tablefmt='plain', colalign=("right", "right", "left", "left")))
    else:
        click.echo(click.style(f'Failed to fetch data for package ID {package_id}. Response Code: {response.status_code}', fg='red'))

@cli.command('log-plants')
@click.argument('plant_ids', type=str)
@click.argument('numback', type=int)
def plant_logs(plant_ids, numback):
    """Fetch and display logs for specified plant IDs and number of logs."""
    url = f'{API_BASE_URL}/plants/logs/{plant_ids}/{numback}/'
    response = requests.get(url)
    data = response.json()

    # Colors for alternating log entries
    log_colors = ['cyan', 'green']

    for index, hit in enumerate(data['hits']['hits']):
        timestamp = hit['_source']['timestamp']
        beat_id = hit['_source']['beat']
        log_color = log_colors[index % 2]  # Alternate colors for each log

        # Styling timestamp and beat ID with the chosen log color
        styled_timestamp = click.style(f"Timestamp: {timestamp}", fg=log_color)
        styled_beat_id = click.style(f"Beat ID: {beat_id}", fg=log_color)
        print(f"{styled_timestamp}, {styled_beat_id}\nResponse:")

        # Assuming the response now directly contains the plant log details
        response = hit['_source']['response']
        plant_color = 'yellow'  # You can change this as needed or make it dynamic

        # Print each key-value pair within the response, applying color to the plant details
        for key, value in response.items():
            if key in ['plant_id', 'plant_name']:
                styled_value = click.style(f"{key}: '{value}'", fg=plant_color)
                print(f"  {styled_value}", end=', ')
            else:
                print(f"{key}: {value}", end=', ')
        print("\n")  # Finish the line after each plant response

        # print("\n" + "-"*40 + "\n")

@cli.command('log-packages')
@click.argument('package_ids', type=str)
@click.argument('numback', type=int)
def package_logs(package_ids, numback):
    """Fetch and display logs for specified package IDs and number of logs."""
    url = f'{API_BASE_URL}/packages/logs/{package_ids}/{numback}/'
    response = requests.get(url)
    data = response.json()

    # Colors for alternating log entries
    log_colors = ['cyan', 'green']
    # List of colors for packages
    package_colors = ['yellow', 'magenta', 'blue', 'red']  # Extend this list as needed

    for index, hit in enumerate(data['hits']['hits']):
        timestamp = hit['_source']['timestamp']
        beat_id = hit['_source']['beat']
        log_color = log_colors[index % 2]  # Alternate colors for each log

        # Styling timestamp and beat ID with the chosen log color
        styled_timestamp = click.style(f"Timestamp: {timestamp}", fg=log_color)
        styled_beat_id = click.style(f"Beat ID: {beat_id}", fg=log_color)
        print(f"{styled_timestamp}, {styled_beat_id}\n")

        for package_index, package in enumerate(hit['_source']['packages']):
            # Sequentially assign colors to packages based on their order
            package_color = package_colors[package_index % len(package_colors)]
            styled_package_id = click.style(f"Package ID: '{package['package_id']}' -", fg=package_color)
            styled_package_name = click.style(f"Package Name: '{package['package_name']}'", fg=package_color)
            print(f"  {styled_package_id} {styled_package_name}")

            for pick in package['picks']:
                # Print each pick with plant details and api fields, with added spacing for clarity
                pick_details = f"    Pick ID: {pick['pick_id']}, Plant ID: {pick['plant_id']}, Plant Name: '{pick['plant_name']}'"
                print(f"{pick_details}")
                for api_field in pick['api_fields']:
                    for key, value in api_field.items():
                        print(f"      {key}: {value}")
            print("")  # Extra newline for spacing between packages

@cli.command('start')
@click.argument('plant_id', type=int)
def start(plant_id):
    """Enable data collection for a plant."""
    url = f'{API_BASE_URL}/plants/{plant_id}/update/'
    update_data = {"collect": 1}
    response = requests.patch(url, json=update_data)
    if response.status_code in [200, 204]:
        click.echo(f"Data collection enabled for plant ID {plant_id}.")
    else:
        click.echo(f"Failed to enable data collection for plant ID {plant_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('stop')
@click.argument('plant_id', type=int)
def stop(plant_id):
    """Disable data collection for a plant."""
    url = f'{API_BASE_URL}/plants/{plant_id}/update/'
    update_data = {"collect": 0}
    response = requests.patch(url, json=update_data)
    if response.status_code in [200, 204]:
        click.echo(f"Data collection disabled for plant ID {plant_id}.")
    else:
        click.echo(f"Failed to disable data collection for plant ID {plant_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('on')
@click.argument('worker_id', type=int)
def on(worker_id):
    """Enable data collection for a worker."""
    url = f'{API_BASE_URL}/workers/{worker_id}/update/'
    update_data = {"status": 1}
    response = requests.patch(url, json=update_data)
    if response.status_code in [200, 204]:
        click.echo(f"Data collection enabled for worker ID {worker_id}.")
    else:
        click.echo(f"Failed to enable data collection for worker ID {worker_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('off')
@click.argument('worker_id', type=int)
def off(worker_id):
    """Disable data collection for a worker."""
    url = f'{API_BASE_URL}/workers/{worker_id}/update/'
    update_data = {"status": 0}
    response = requests.patch(url, json=update_data)
    if response.status_code in [200, 204]:
        click.echo(f"Data collection disabled for worker ID {worker_id}.")
    else:
        click.echo(f"Failed to disable data collection for worker ID {worker_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('enable')
@click.argument('action_id', type=int)
def enable_action(action_id):
    """Enable an action."""
    url = f'{API_BASE_URL}/actions/{action_id}/'
    update_data = {"status": 1}  # Set status to 'ON'
    response = requests.patch(url, json=update_data)
    if response.status_code in [200, 204]:
        click.echo(f"Action ID {action_id} enabled.")
    else:
        click.echo(f"Failed to enable action ID {action_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('disable')
@click.argument('action_id', type=int)
def disable_action(action_id):
    """Disable an action."""
    url = f'{API_BASE_URL}/actions/{action_id}/'
    update_data = {"status": 0}  # Set status to 'OFF'
    response = requests.patch(url, json=update_data)
    if response.status_code in [200, 204]:
        click.echo(f"Action ID {action_id} disabled.")
    else:
        click.echo(f"Failed to disable action ID {action_id}. Status code: {response.status_code}, Response: {response.text}")

@cli.command('list-workers')
def list_workers():
    """List all workers with associated plant and paths counts."""
    url = f'{API_BASE_URL}/workers/'
    response = requests.get(url)
    workers_data = response.json()

    table = []
    for worker in workers_data:

        if worker['resume'] == 'OFF':
            status = click.style(worker['resume'])
        elif worker['resume'] == 'DOWN':
            status = click.style(worker['resume'], fg='red')
        elif worker['resume'] == 'STOP':
            status = click.style(worker['resume'], fg='yellow')
        elif worker['resume'] == 'ONLINE':
            status = click.style(worker['resume'], fg='cyan')

        worker_id = worker['id']
        worker_name = worker['name']
        plants_count = len(worker['package']['picks'])
        paths_count = sum(len(pick['paths']) for pick in worker['package']['picks'])
        since = worker['since']
        table.append([worker_id, worker_name, plants_count, paths_count, status, since])

    headers = ['ID', 'NAME', 'PLANTS', 'FIELDS', 'STATUS', 'SINCE']
    click.echo(tabulate(table, headers=headers, tablefmt='plain'))

@cli.command('add-worker')
def create_worker():
    """Create a new worker."""
    name = click.prompt('Enter worker name')
    description = click.prompt('Enter worker description')
    url = f'{API_BASE_URL}/workers/create/'
    data = {
        'name': name,
        'description': description
    }
    response = requests.post(url, json=data)
    if response.ok:
        click.echo("Worker created successfully.")
    else:
        click.echo("Failed to create worker.")


@cli.command('edit-worker')
@click.argument('id', type=int)
def edit_worker(id):
    """Update an existing worker's name and description."""
    click.echo("Fetching current worker details...")
    get_url = f'{API_BASE_URL}/workers/{id}/'
    get_response = requests.get(get_url)
    if not get_response.ok:
        click.echo(f"Failed to fetch details for worker with ID {id}.")
        return

    worker_data = get_response.json()
    click.echo(f"Current worker name: {worker_data['name']}")
    click.echo(f"Current worker description: {worker_data['description']}")

    name = click.prompt('Enter new worker name', default=worker_data['name'])
    description = click.prompt('Enter new worker description', default=worker_data['description'])

    update_url = f'{API_BASE_URL}/workers/{id}/update/'
    update_data = {'name': name, 'description': description}
    update_response = requests.patch(update_url, json=update_data)
    if update_response.ok:
        click.echo("Worker updated successfully.")
    else:
        click.echo("Failed to update worker.")


@cli.command('edit-package')
@click.argument('worker_id', type=int)
def edit_package(worker_id):
    """Update the package of a worker's name and description."""
    click.echo("Fetching current package details...")
    get_url = f'{API_BASE_URL}/workers/{worker_id}/'
    get_response = requests.get(get_url)
    if not get_response.ok:
        click.echo(f"Failed to fetch details for worker with ID {worker_id}.")
        return

    worker_data = get_response.json()
    package_data = worker_data['package']
    click.echo(f"Current package name: {package_data['name']}")
    click.echo(f"Current package description: {package_data['description']}")

    name = click.prompt('Enter new package name', default=package_data['name'])
    description = click.prompt('Enter new package description', default=package_data['description'])

    update_url = f'{API_BASE_URL}/workers/{worker_id}/update/'
    update_data = {
        'package': {
            'name': name,
            'description': description
        }
    }
    update_response = requests.patch(update_url, json=update_data)
    if update_response.ok:
        click.echo("Package updated successfully.")
    else:
        click.echo("Failed to update package.")

@cli.command('add-pick')
@click.argument('worker_id', type=int)
def add_pick(worker_id):
    """Add a new pick to a worker."""
    click.echo("Fetching current picks...")
    get_url = f'{API_BASE_URL}/workers/{worker_id}/'
    get_response = requests.get(get_url)
    if not get_response.ok:
        click.echo(f"Failed to fetch details for worker with ID {worker_id}.")
        return

    worker_data = get_response.json()
    existing_plant_ids = [pick['plant_id'] for pick in worker_data['package']['picks']]

    plant_id = click.prompt('Enter plant ID')
    if int(plant_id) in existing_plant_ids:
        click.echo(f"A pick with plant ID {plant_id} already exists for this worker.")
        return

    paths = []
    while True:
        path = click.prompt('Enter path (leave empty to finish)', default='')
        if not path:
            break
        paths.append(path)

    url = f'{API_BASE_URL}/workers/{worker_id}/update/'
    data = {
        'picks': [
            {
                'plant_id': int(plant_id),
                'paths': paths
            }
        ]
    }
    response = requests.put(url, json=data)
    if response.ok:
        click.echo("Pick added successfully.")
    else:
        click.echo("Failed to add pick.")

@cli.command('edit-pick')
@click.argument('worker_id', type=int)
def edit_pick(worker_id):
    """Edit an existing pick of a worker."""
    click.echo("Fetching current pick details...")
    get_url = f'{API_BASE_URL}/workers/{worker_id}/'
    get_response = requests.get(get_url)
    if not get_response.ok:
        click.echo(f"Failed to fetch details for worker with ID {worker_id}.")
        return

    worker_data = get_response.json()
    picks_data = worker_data['package']['picks']
    if not picks_data:
        click.echo("No picks found for this worker.")
        return

    # Displaying picks with a count for user to select
    for i, pick in enumerate(picks_data, start=1):
        click.echo(f"Pick #{i}: Plant ID {pick['plant_id']}")

    pick_number = click.prompt('Enter the number of the pick to edit', type=int)
    if pick_number > len(picks_data) or pick_number < 1:
        click.echo(f"Invalid pick number. Please enter a number between 1 and {len(picks_data)}.")
        return

    # Selecting the pick based on user input
    current_pick = picks_data[pick_number - 1]
    click.echo(f"Editing pick #{pick_number} for plant ID {current_pick['plant_id']}:")

    # Editing paths within the selected pick
    for i, path in enumerate(current_pick['paths'], start=1):
        new_path = click.prompt(f"Enter new path for Pick #{pick_number} Path #{i} (leave empty to keep as is)", default=path)
        if new_path:  # Only update if user enters something
            current_pick['paths'][i - 1] = new_path

    # Optionally, ask for new paths to be added to the pick
    while True:
        new_path = click.prompt("Enter new path for a new Pick (leave empty to finish)", default='')
        if not new_path:
            click.echo("No new paths entered. Exiting...")
            break
        current_pick['paths'].append(new_path)

    # Updating the pick in the API
    url = f'{API_BASE_URL}/workers/{worker_id}/update/'
    data = {
        'picks': [
            {
                'plant_id': current_pick['plant_id'],
                'paths': current_pick['paths']
            }
        ]
    }
    response = requests.put(url, json=data)
    if response.ok:
        click.echo(f"Pick #{pick_number} edited successfully.")
    else:
        click.echo("Failed to edit pick.")

@cli.command('remove-pick')
@click.argument('worker_id', type=int)
def remove_pick(worker_id):
    """Remove a pick from a worker."""
    click.echo("Fetching current pick details...")
    get_url = f'{API_BASE_URL}/workers/{worker_id}/'
    get_response = requests.get(get_url)
    if not get_response.ok:
        click.echo(f"Failed to fetch details for worker with ID {worker_id}.")
        return

    worker_data = get_response.json()
    picks_data = worker_data['package']['picks']
    if not picks_data:
        click.echo("No picks found for this worker.")
        return

    count = click.prompt('Enter the count of the pick to remove', type=int)
    if count > len(picks_data):
        click.echo(f"Invalid pick count. Worker has only {len(picks_data)} picks.")
        return

    plant_id = picks_data[count - 1]['plant_id']
    click.confirm(f"Are you sure you want to remove pick #{count} with plant ID {plant_id}?", abort=True)

    url = f'{API_BASE_URL}/workers/{worker_id}/remove-pick/'
    data = {'plant_id': plant_id}
    response = requests.put(url, json=data)
    if response.ok:
        click.echo("Pick removed successfully.")
    else:
        click.echo("Failed to remove pick.")

@cli.command('watch-worker')
@click.argument('workerid', type=int)
def watch_worker(workerid):
    """Display detailed information about a worker, with each pick in a new section below."""
    url = f'{API_BASE_URL}/workers/{workerid}/'
    response = requests.get(url)
    if not response.ok:
        click.echo(f"Failed to fetch details for worker with ID {workerid}.")
        return

    worker_data = response.json()

    # Worker details
    worker_details = [
        ["Name:", worker_data['name']],
        ["", ""],
        ["Unit Description:", worker_data['description']],
        ["", ""],
        ["Data Description:", worker_data['package']['description']],
        ["", ""],
        ["", ""],
    ]

    # Print worker details
    click.echo(tabulate(worker_details, tablefmt="plain"))

    # Picks details
    pick_table = []
    pick_number = 1
    for pick in worker_data['package']['picks']:
        plant_id = pick['plant_id']
        plant_url = f"{API_BASE_URL}/plants/{plant_id}/"
        plant_response = requests.get(plant_url)

        if plant_response.ok:
            plant_data = plant_response.json()
            plant_name = plant_data['name']
            plant_status = plant_data.get('status', 0)
            plant_collect = plant_data.get('collect', 0)

            if plant_status == 1 and plant_collect == 1:
                plant_name_colored = click.style(plant_name, fg='cyan')
            elif plant_status == 1:
                plant_name_colored = click.style(plant_name, fg='yellow')
            else:
                plant_name_colored = click.style(plant_name, fg='red')
        else:
            plant_name_colored = click.style("NOT FOUND", fg='red')

        pick_table.append([f"Pick N°{pick_number}:", plant_name_colored])
        pick_number += 1
        pick_table.extend([["", path] for path in pick['paths']])
        pick_table.append(["", ""])
    # Print pick details
    click.echo(tabulate(pick_table, tablefmt="plain"))

@cli.command('edit-picks')
@click.argument('worker_id', type=int)
def edit_picks(worker_id):
    """Edit the picks of a worker's package in YAML format with specific spacing and order."""
    # Fetch current worker details to get picks
    get_url = f'{API_BASE_URL}/workers/{worker_id}/'
    get_response = requests.get(get_url)

    if not get_response.ok:
        click.echo(f"Failed to fetch details for worker with ID {worker_id}.")
        return

    worker_data = get_response.json()
    picks = worker_data['package']['picks']

    # Remove 'id' from picks and ensure 'plant_id' is above 'paths'
    formatted_picks = [{'plant_id': pick['plant_id'], 'paths': pick['paths']} for pick in picks]

    # Convert picks to YAML format with desired structure and spacing
    picks_yaml = yaml.dump(formatted_picks, sort_keys=False, default_flow_style=False, indent=2)

    # Add extra newline between items for clarity
    picks_yaml = picks_yaml.replace('\n- ', '\n\n- ')

    # Open text editor with current picks data in YAML format
    edited_picks_yaml = click.edit(text=picks_yaml, require_save=False, extension='.yml')

    if edited_picks_yaml is None:
        click.echo("No changes made to picks.")
        return

    # Load edited YAML back into Python object
    try:
        edited_picks = yaml.safe_load(edited_picks_yaml)
    except yaml.YAMLError as e:
        click.echo(f"Error parsing YAML: {e}")
        return

    # Update worker's package picks
    update_url = f'{API_BASE_URL}/workers/{worker_id}/update/'
    update_data = {"picks": edited_picks}
    update_response = requests.patch(update_url, json=update_data)

    if update_response.ok:
        click.echo("Package picks updated successfully.")
    else:
        click.echo(f"Failed to update package picks. Response: {update_response.text}")
