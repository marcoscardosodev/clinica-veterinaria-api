from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import main


@pytest.fixture
def setup_api():
    with TemporaryDirectory() as folder:
        engine = create_engine(f'sqlite:///{Path(folder) / "test.db"}', connect_args={'check_same_thread': False})
        main.Base.metadata.create_all(engine)
        factory = sessionmaker(bind=engine)
        user = {'uid': 'vet_a'}

        def db_override():
            with factory() as session:
                yield session

        main.app.dependency_overrides[main.get_db] = db_override
        main.app.dependency_overrides[main.veterinario_atual] = lambda: user['uid']
        with TestClient(main.app) as client:
            yield client, user
        main.app.dependency_overrides.clear()
        engine.dispose()


def test_crud_isolado_por_veterinario(setup_api):
    client, user = setup_api
    dados = {'nome': 'Rex', 'especie': 'Cão', 'raca': 'Labrador', 'idade': 4, 'nome_tutor': 'Ana'}
    res = client.post('/animais', json=dados)
    assert res.status_code == 201
    animal = res.json()
    assert animal['veterinario_id'] == 'vet_a'
    id = animal['id']
    assert len(client.get('/animais').json()) == 1
    assert client.get(f'/animais/{id}').status_code == 200
    assert client.post('/animais', json={**dados, 'veterinario_id': 'vet_b'}).status_code == 422

    user['uid'] = 'vet_b'
    assert client.get('/animais').json() == []
    assert client.get(f'/animais/{id}').status_code == 404
    assert client.put(f'/animais/{id}', json=dados).status_code == 404
    assert client.delete(f'/animais/{id}').status_code == 404

    user['uid'] = 'vet_a'
    res = client.put(f'/animais/{id}', json={**dados, 'idade': 5})
    assert res.status_code == 200 and res.json()['idade'] == 5
    assert client.delete(f'/animais/{id}').status_code == 204
    assert client.get(f'/animais/{id}').status_code == 404


def test_validacao(setup_api):
    client, _ = setup_api
    dados = {'nome': '', 'especie': 'Cão', 'raca': 'Labrador', 'idade': -1, 'nome_tutor': 'Ana'}
    assert client.post('/animais', json=dados).status_code == 422
