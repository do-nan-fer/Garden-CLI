import click
import requests
import tempfile
import os
import yaml
from tabulate import tabulate
from datetime import datetime, timezone

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

        last_status_change = datetime.fromisoformat(plant['last_status_change'].replace('Z', '+00:00'))
        last_status_change = last_status_change.replace(tzinfo=timezone.utc)

        time_since_change = datetime.utcnow().replace(tzinfo=timezone.utc) - last_status_change

        since = int(time_since_change.total_seconds())
        if since < 60:
            since_str = f"{since} S"
        elif since < 3600:
            since_str = f"{since // 60} M"
        elif since < 86400:
            since_str = f"{since // 3600} H"
        else:
            since_str = f"{since // 86400} D"

        table.append([plant['id'], plant['name'], plant.get('picks_count', 0), collect, status, since_str])

    headers = ['ID', 'NAME', 'PICKS', 'COLLECT', 'STATUS', 'SINCE']
    click.echo(tabulate(table, headers=headers, tablefmt='plain'))

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
    excluded_fields = ['id', 'collect', 'status', 'last_status_change']  # Added 'last_status_change' to the exclusion list
    editable_data = {key: plant_data[key] for key in plant_data if key not in excluded_fields}

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

@cli.command('watch-plant')
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

@cli.command('logs-plants')
@click.argument('plant_ids', type=str)
@click.argument('numback', type=int)
def plant_logs(plant_ids, numback):
    """Fetch and display logs for specified plant IDs and number of logs."""
    url = f'{API_BASE_URL}/plants/logs/{plant_ids}/{numback}/'
    response = requests.get(url)
    data = response.json()

    # Colors for alternating log entries
    log_colors = ['cyan', 'green']
    # List of colors for plants
    plant_colors = ['yellow', 'magenta', 'blue', 'red']  # Extend this list as needed

    for index, hit in enumerate(data['hits']['hits']):
        timestamp = hit['_source']['timestamp']
        beat_id = hit['_source']['beat']
        log_color = log_colors[index % 2]  # Alternate colors for each log

        # Styling timestamp and beat ID with the chosen log color
        styled_timestamp = click.style(f"Timestamp: {timestamp}", fg=log_color)
        styled_beat_id = click.style(f"Beat ID: {beat_id}", fg=log_color)
        print(f"{styled_timestamp}, {styled_beat_id}\nResponses:")

        for plant_index, response in enumerate(hit['_source']['responses']):
            # Sequentially assign colors to plants based on their order
            plant_color = plant_colors[plant_index % len(plant_colors)]

            # Print each key-value pair within the response, applying color to the plant details
            for key, value in response.items():
                if key in ['plant_id', 'plant_name']:
                    styled_value = click.style(f"{key}: '{value}'", fg=plant_color)
                    print(f"  {styled_value}", end=', ')
                else:
                    print(f"{key}: {value}", end=', ')
            print("\n")  # Finish the line after each plant response

       # print("\n" + "-"*40 + "\n")

@cli.command('logs-packages')
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

@cli.command('list-packages')
def list_packages():
    """Listar todos los paquetes disponibles."""
    url = f'{API_BASE_URL}/packages/'
    response = requests.get(url)
    data = response.json()

    packages = data

    table = []
    for package in packages:
        table.append([package['id'], package['name'], package['unique_plants_count'], package['unique_api_fields_count']])

    headers = ['ID', 'Nombre', 'PLANTS', 'FIELDS']
    click.echo(tabulate(table, headers=headers, tablefmt='plain'))


@cli.command('add-package')
@click.option('--name', prompt='Nombre del paquete', help='Nombre del paquete')
@click.option('--description', prompt='Descripción del paquete', help='Descripción del paquete')
@click.option('--plant-ids', prompt='IDs de las plantas (separados por coma)', help='IDs de las plantas separados por coma')
def add_package(name, description, plant_ids):
    """Agregar un nuevo paquete con los campos especificados."""
    try:
        plant_ids = [int(plant_id.strip()) for plant_id in plant_ids.split(',')]
    except ValueError:
        click.echo("Por favor, ingresa solo números enteros separados por comas para los IDs de las plantas.")
        return

    all_picks = []

    for plant_id in plant_ids:
        fields = get_plant_data(plant_id)
        if not fields:
            click.echo(f"No se encontraron datos para la planta con ID {plant_id}.")
            continue

        pick_data = {'plant': plant_id, 'api_fields': []}
        click.echo(f"Ingrese los detalles para el Pick asociado a la planta {plant_id}:")

        while True:
            field_name = click.prompt(f"Nombre del campo para la planta {plant_id}", default='', show_default=False)
            if not field_name:
                break

            if field_exists(field_name, fields):
                pick_data['api_fields'].append({'name': field_name})
            else:
                click.echo(f"El campo '{field_name}' no existe en la planta {plant_id}. Intente nuevamente.")

        if pick_data['api_fields']:
            pick_id = create_pick(pick_data)
            if pick_id:
                all_picks.append(pick_id)

    if all_picks:
        package_id = create_package(name, description, all_picks)
        if package_id:
            click.echo(f"Package creado exitosamente con ID {package_id}.")
    else:
        click.echo("No se crearon Picks. Abortando la creación del paquete.")

def create_pick(pick_data):
    """Crea un Pick y devuelve su ID."""
    url = f'{API_BASE_URL}/picks/add/'
    response = requests.post(url, json={'plant': pick_data['plant'], 'api_fields': pick_data['api_fields']})
    if response.status_code in [200, 201]:  # Asumiendo que el código de estado exitoso puede ser 200 o 201
        return response.json().get('id')
    else:
        click.echo(f"Error al crear Pick para la planta {pick_data['plant']}: {response.status_code}")
        return None

def create_package(name, description, pick_ids):
    """Crea un Package con los Picks dados y devuelve su ID."""
    url = f'{API_BASE_URL}/packages/add/'
    response = requests.post(url, json={'name': name, 'description': description, 'picks': pick_ids})
    if response.status_code in [200, 201]:  # Asumiendo que el código de estado exitoso puede ser 200 o 201
        return response.json().get('id')
    else:
        click.echo(f"Error al crear Package '{name}': {response.status_code}")
        return None

def get_plant_data(plant_id):
    """Obtiene los nombres de los campos del último log de una planta específica, incluyendo campos anidados."""
    url = f'{API_BASE_URL}/logs/{plant_id}/1/'
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        hits = data.get('hits', {}).get('hits', [])
        if hits:
            plant_responses = hits[0].get('_source', {}).get('responses', [])
            for response in plant_responses:
                if str(response.get('plant_id')) == str(plant_id):
                    return extract_fields(response.get('response', {}))
    else:
        click.echo(f"Error al obtener datos de la planta {plant_id}: {response.status_code}")
        return set()

def extract_fields(data, parent_key=''):
    """Extrae todos los campos, incluyendo anidados, de un objeto de datos."""
    fields = set()
    for key, value in data.items():
        full_key = f'{parent_key}.{key}' if parent_key else key
        if isinstance(value, dict):
            fields.update(extract_fields(value, full_key))
        else:
            fields.add(full_key)
    return fields

def field_exists(field_name, fields):
    """Verifica si el campo especificado existe, considerando campos anidados."""
    return field_name in fields

def get_field_color(field_id):
    """Obtiene el color del campo."""
    field_url = f'{API_BASE_URL}/api-fields/{field_id}/'
    response = requests.get(field_url)
    if response.status_code == 200:
        return 'cyan'
    else:
        return 'magenta'

@cli.command('watch-package')
@click.argument('package_id', type=int)
def watch_package(package_id):
    """Consulta un paquete y muestra las plantas y sus campos asociados."""
    package_url = f'{API_BASE_URL}/packages/{package_id}/'
    package_response = requests.get(package_url)
    if package_response.status_code != 200:
        click.echo(f'Error al consultar el paquete. Código de estado: {package_response.status_code}')
        return
    package_data = package_response.json()

    picks = package_data.get('picks', [])
    if not picks:
        click.echo('No se encontraron picks asociados al paquete.')
        return

    for pick_id in picks:
        pick_url = f'{API_BASE_URL}/picks/{pick_id}/'
        pick_response = requests.get(pick_url)
        if pick_response.status_code != 200:
            click.echo(f'Error al consultar el pick {pick_id}. Código de estado: {pick_response.status_code}')
            continue
        pick_data = pick_response.json()

        plant_id = pick_data.get('plant')
        api_fields = pick_data.get('api_fields', [])

        # Consultar la información de la planta para obtener el nombre
        plant_url = f'{API_BASE_URL}/plants/{plant_id}/'
        plant_response = requests.get(plant_url)
        if plant_response.status_code != 200:
            click.echo(f'Error al consultar la planta {plant_id}. Código de estado: {plant_response.status_code}')
            continue
        plant_data = plant_response.json()
        plant_name = plant_data.get('name', f'Planta {plant_id}')  # Usar el nombre de la planta, o "Planta {plant_id}" como fallback

        plant_fields = get_plant_data(plant_id)
        if not plant_fields:
            click.echo(f'No se encontraron datos para la planta con ID {plant_id}.')
            continue

        # Mostrar nombre de la planta
        click.echo(f'{plant_name}:')

        for field in api_fields:
            field_name = field.get('name')
            color = 'cyan' if field_exists(field_name, plant_fields) else 'magenta'
            click.echo(click.style(f'  - {field_name}', fg=color))


@cli.command('remove-package')
@click.argument('package_id', type=int)
def delete_package(package_id):
    """Elimina un paquete existente utilizando su package_id."""
    delete_url = f'{API_BASE_URL}/packages/{package_id}/delete/'
    response = requests.delete(delete_url)
    if response.status_code in [200, 204]:  # Asumiendo que 200 o 204 son respuestas exitosas para una operación de eliminación
        click.echo(f"Paquete con ID {package_id} eliminado exitosamente.")
    else:
        click.echo(f"Error al eliminar el paquete con ID {package_id}. Código de estado: {response.status_code}")

