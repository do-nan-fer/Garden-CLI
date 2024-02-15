import click
import requests
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
    url = f'{API_BASE_URL}/plants/{plant_id}/' if plant_id else f'{API_BASE_URL}/plants/'
    response = requests.get(url)
    data = response.json()

    # Ensure data is in a list format whether it's a single plant or multiple
    plants = [data] if plant_id else data

    # Modify table data based on collect and status values
    table = []
    for plant in plants:
        if plant['collect'] == 0:
            collect = click.style('NO')
            status = click.style('  -')
        else:
            collect = click.style('YES')
            if plant['status'] == 0:
                status = click.style('DEAD', fg='magenta')
            else:
                status = click.style('ALIVE', fg='cyan')

        table.append([plant['id'], plant['name'], plant.get('picks_count', 0), collect, status])

    click.echo(tabulate(table, headers=['ID', 'NAME', 'PICKS', 'COLLECT', 'STATUS'], tablefmt='plain'))

