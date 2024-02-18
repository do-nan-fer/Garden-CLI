import click
import requests
import tempfile
import os
import yaml
from tabulate import tabulate

API_BASE_URL = 'http://192.168.101.14:8500'  # Adjust the base URL as needed

@click.group()
def cli():
    """Garden CLI tool."""
    pass

@cli.command('list-plants')
@click.argument('plant_id', type=int, required=False)
def list_plants(plant_id=None):
    """List all plants or a single plant by ID."""
    url = f'{API_BASE_URL}/available/' if plant_id else f'{API_BASE_URL}/plants/'
    response = requests.get(url)
    data = response.json()

    plants = [data] if plant_id else data

    table = []
    for plant in plants:
        collect = 'YES' if plant['collect'] == 1 else 'NO'
        if plant['status'] == 1:
            status = click.style('ALIVE', fg='cyan')
        else:
            status = click.style('DEAD', fg='magenta')
        table.append([plant['id'], plant['name'], plant.get('picks_count', 0), collect, status])
    click.echo(tabulate(table, headers=['ID', 'NAME', 'PICKS', 'COLLECT', 'STATUS'], tablefmt='plain'))

@cli.command('add-plant')
def add_plant():
    """Add a new plant by interactively asking for each field."""
    # Prompt for each field
    name = click.prompt('Name', type=str)
    description = click.prompt('Description', type=str)
    full_query_command = click.prompt('Command', type=str)

    # Create a dictionary for the plant data
    plant_data = {
        "name": name,
        "description": description,
        "full_query_command": full_query_command
        # 'collect' and 'status' will default to 0 and are not included here
    }

    # Send a POST request to the API
    url = f'{API_BASE_URL}/plants/add/'
    response = requests.post(url, json=plant_data)

    if response.status_code in [200, 201]:
        click.echo(f"Plant '{name}' added successfully.")
    else:
        click.echo(f"Failed to add plant. Status code: {response.status_code}, Response: {response.text}")

@cli.command('edit-plant')
@click.argument('plant_id', type=int)
def edit_plant(plant_id):
    """Edit details of a plant without changing its ID, collect status, or plant status."""
    url = f'{API_BASE_URL}/plants/{plant_id}/'
    response = requests.get(url)
    if response.status_code != 200:
        click.echo(f"Failed to fetch plant with ID {plant_id}. Status code: {response.status_code}, Response: {response.text}")
        return

    plant_data = response.json()
    original_collect = plant_data['collect']
    original_status = plant_data['status']

    # Remove non-editable fields from the editable template
    editable_data = {key: plant_data[key] for key in plant_data if key not in ['id', 'collect', 'status']}

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode='w+', delete=False) as tf:
        yaml.dump(editable_data, tf, allow_unicode=True)
        tf.flush()
        click.echo("Opening Vim editor for you to edit plant details...")
        os.system(f'vim {tf.name}')
        tf.seek(0)
        updated_plant_data = yaml.safe_load(tf)

    os.unlink(tf.name)  # Clean up the temporary file

    # Reset non-editable fields to their original values
    updated_plant_data['collect'] = original_collect
    updated_plant_data['status'] = original_status

    # Use PATCH instead of PUT for the update
    update_response = requests.patch(url + 'update/', json=updated_plant_data)  # Adjusted to use PATCH and the correct endpoint
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

@cli.command('watch')
@click.argument('plant_id', type=int, required=True)
def watch_plant(plant_id):
    """Watch a specific plant by ID."""
    url = f'{API_BASE_URL}/plants/{plant_id}/data/'
    response = requests.get(url)
    
    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()

        # Prepare the table content
        table = []
        count = 1
        for key, value in data.items():
            # Remove "response" from the beginning of the key if it's there
            display_key = key.replace("response.", "") if key.startswith("response") else key

            # Apply cute green color style to the value
            colored_value = click.style(str(value), fg='bright_green')  # Use 'green' or 'bright_green'

            table.append([count, display_key, colored_value])
            count += 1

        # Display the table
        click.echo(tabulate(table, headers=['COUNT', 'FIELDNAME', 'FIELDVALUE'], tablefmt='plain'))
    else:
        click.echo(click.style(f'Failed to fetch data for plant ID {plant_id}. Response Code: {response.status_code}', fg='red'))

@cli.command('collect')
@click.argument('plant_id', type=int)
def collect(plant_id):
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

