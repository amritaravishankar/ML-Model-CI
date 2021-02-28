#  Copyright (c) NTU_CAP 2021. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at:
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express
#  or implied. See the License for the specific language governing
#  permissions and limitations under the License.
from pathlib import Path
from typing import Dict, List, Optional

import click
import requests
import typer

from modelci.app import SERVER_HOST, SERVER_PORT
from modelci.hub.manager import register_model_from_yaml
from modelci.hub.publish import _download_model_from_url
from modelci.types.models import Framework, Engine, IOShape, Task, Metric, MLModelInForm
from modelci.ui import model_view
from modelci.utils import Logger
from modelci.utils.misc import remove_dict_null

logger = Logger(__name__)

app = typer.Typer()


@click.group()
def modelhub():
    pass


@modelhub.command("publish")
@click.option('-p', '--ymal_path', required=True, type=str, help='the yaml file path')
def register_model(ymal_path):
    """publish a model to our system

    Args:
        ymal_path ([type]): a ymal file that contains model registeration info
    """

    register_model_from_yaml(ymal_path)
    logger.info("model published")


@app.command()
def publish(
        file_or_dir: Path = typer.Argument(..., help='Model weight files', exists=True),
        architecture: str = typer.Option(..., '-name', '--architecture', help='Architecture'),
        framework: Framework = typer.Option(..., '-f', '--framework', help='Framework'),
        engine: Engine = typer.Option(..., '-e', '--engine', help='Engine'),
        version: int = typer.Option(..., '-v', '--version', min=1, help='Version number'),
        task: Task = typer.Option(..., '-t', '--task', help='Task'),
        dataset: str = typer.Option(..., '-d', '--dataset', help='Dataset name'),
        metric: Dict[Metric, float] = typer.Option(
            ...,
            help='Metrics in the form of mapping JSON string. The map type is '
                 '`Dict[types.models.mlmodel.Metric, float]`. An example is \'{"acc": 0.76}.\'',
        ),
        inputs: List[IOShape] = typer.Option(
            ...,
            '-i', '--input',
            help='List of shape definitions for input tensors. An example of one shape definition is '
                 '\'{"name": "input", "shape": [-1, 3, 224, 224], "dtype": "TYPE_FP32", "format": "FORMAT_NCHW"}\'',
        ),
        outputs: List[IOShape] = typer.Option(
            ...,
            '-o', '--output',
            help='List of shape definitions for output tensors. An example of one shape definition is '
                 '\'{"name": "output", "shape": [-1, 1000], "dtype": "TYPE_FP32"}\'',
        ),
        convert: Optional[bool] = typer.Option(
            True,
            '-c', '--convert',
            help='Convert the model to other possible format.',
        ),
        profile: Optional[bool] = typer.Option(
            False,
            '-p', '--profile',
            help='Profile the published model(s).',
        ),
):
    payload = {'convert': convert, 'profile': profile}
    model_in_form = MLModelInForm(
        architecture=architecture, framework=framework, engine=engine, version=version, dataset=dataset,
        metric=metric, task=task, inputs=inputs, outputs=outputs
    )
    data = model_in_form.dict(exclude_none=True, use_enum_values=True)
    form_data = {k: str(v) for k, v in data.items()}

    files = list()
    key = 'files'
    try:
        # read weight file
        if file_or_dir.is_dir():
            for file in filter(Path.is_file, file_or_dir.rglob('*')):
                name = Path(file).relative_to(file_or_dir.parent)
                files.append((key, (str(name), open(file, 'rb'), 'application/example')))
        else:
            files.append((key, (file_or_dir.name, open(file_or_dir, 'rb'), 'application/example')))

        with requests.post(
                f'http://{SERVER_HOST}:{SERVER_PORT}/api/v1/model/',
                params=payload, data=form_data, files=files,
        ) as r:
            typer.echo(r.json())
    finally:
        for file in files:
            file[1][1].close()


@modelhub.command("list")
@click.argument('name', type=click.STRING, required=False)
@click.option(
    '-f', '--framework',
    type=click.Choice(['TensorFlow', 'PyTorch'], case_sensitive=False),
    help='Model framework.'
)
@click.option(
    '-e', '--engine',
    type=click.Choice(['NONE', 'TFS', 'TORCHSCRIPT', 'ONNX', 'TRT', 'TVM', 'CUSTOMIZED'], case_sensitive=False),
    help='Model serving engine.'
)
@click.option('-v', '--version', type=click.INT, help='Model version.')
@click.option('-a', '--all', 'list_all', type=click.BOOL, is_flag=True, help='Show all models.')
def show_models(name, framework, engine, version, list_all):
    """show a table that lists all models published in mlmodelci

    Args:
        name ([type]): [description]
        framework ([type]): [description]
        engine ([type]): [description]
        version ([type]): [description]
        list_all ([type]): [description]
    """
    payload = remove_dict_null({'name': name, 'framework': framework, 'engine': engine, 'version': version})
    with requests.get(f'http://{SERVER_HOST}:{SERVER_PORT}/api/v1/model/', params=payload) as r:
        model_list = r.json()
        model_view([model_list], list_all=list_all)


@modelhub.command()
def download_model():
    raise NotImplementedError


@modelhub.command("get")
@click.option('-u', '--url', required=True, type=str, help='the link to a model')
@click.option('-p', '--path', required=True, type=str, help='the saved path and file name.')
def download_model_from_url(url, path):
    """download a model weight file from an url

    Args:
        url ([type]): a model file url
        path ([type]): the saved path and file name
    """
    _download_model_from_url(url, path)
    logger.info("{} model downloaded succussfuly.".format(path))
