import os
from contextlib import asynccontextmanager
from typing import Annotated

import firebase_admin
from firebase_admin import auth, credentials
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import ForeignKey, Integer, String, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./clinica.db')
connect_args = {'check_same_thread': False} if DATABASE_URL.startswith('sqlite') else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class Animal(Base):
    __tablename__ = 'animais'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    especie: Mapped[str] = mapped_column(String(80), nullable=False)
    raca: Mapped[str] = mapped_column(String(80), nullable=False)
    idade: Mapped[int] = mapped_column(Integer, nullable=False)
    nome_tutor: Mapped[str] = mapped_column(String(120), nullable=False)
    veterinario_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)


class AnimalDados(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    nome: str = Field(min_length=1, max_length=120)
    especie: str = Field(min_length=1, max_length=80)
    raca: str = Field(min_length=1, max_length=80)
    idade: int = Field(ge=0)
    nome_tutor: str = Field(min_length=1, max_length=120)


class AnimalResposta(AnimalDados):
    model_config = ConfigDict(from_attributes=True)
    id: int
    veterinario_id: str


def iniciar_firebase():
    if firebase_admin._apps:
        return
    cred_path = os.getenv('FIREBASE_CREDENTIALS')
    if cred_path:
        firebase_admin.initialize_app(credentials.Certificate(cred_path))
    else:
        # Credenciais padrão do Google, configuráveis por GOOGLE_APPLICATION_CREDENTIALS.
        firebase_admin.initialize_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    iniciar_firebase()
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title='API Clínica Veterinária', version='1.0.0', lifespan=lifespan)
security = HTTPBearer(auto_error=False)


def get_db():
    with SessionLocal() as db:
        yield db


def veterinario_atual(
    cred: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
) -> str:
    if cred is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token de autenticação obrigatório',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    try:
        usuario = auth.verify_id_token(cred.credentials, check_revoked=True)
        return usuario['uid']
    except (auth.InvalidIdTokenError, auth.ExpiredIdTokenError,
            auth.RevokedIdTokenError, auth.UserDisabledError, ValueError, KeyError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Token inválido, expirado ou revogado',
            headers={'WWW-Authenticate': 'Bearer'},
        )
    except Exception:
        # Falhas de comunicação com Firebase não significam token inválido.
        raise HTTPException(status_code=503, detail='Serviço de autenticação indisponível')


Db = Annotated[Session, Depends(get_db)]
Veterinario = Annotated[str, Depends(veterinario_atual)]


def animal_do_veterinario(db: Session, animal_id: int, uid: str) -> Animal:
    animal = db.scalar(select(Animal).where(Animal.id == animal_id, Animal.veterinario_id == uid))
    if animal is None:
        raise HTTPException(status_code=404, detail='Animal não encontrado')
    return animal


@app.post('/animais', response_model=AnimalResposta, status_code=201)
def cadastrar_animal(dados: AnimalDados, db: Db, uid: Veterinario):
    animal = Animal(**dados.model_dump(), veterinario_id=uid)
    db.add(animal)
    db.commit()
    db.refresh(animal)
    return animal


@app.get('/animais', response_model=list[AnimalResposta])
def listar_animais(db: Db, uid: Veterinario):
    return db.scalars(select(Animal).where(Animal.veterinario_id == uid).order_by(Animal.id)).all()


@app.get('/animais/{id}', response_model=AnimalResposta)
def consultar_animal(id: int, db: Db, uid: Veterinario):
    return animal_do_veterinario(db, id, uid)


@app.put('/animais/{id}', response_model=AnimalResposta)
def atualizar_animal(id: int, dados: AnimalDados, db: Db, uid: Veterinario):
    animal = animal_do_veterinario(db, id, uid)
    for campo, valor in dados.model_dump().items():
        setattr(animal, campo, valor)
    db.commit()
    db.refresh(animal)
    return animal


@app.delete('/animais/{id}', status_code=204)
def excluir_animal(id: int, db: Db, uid: Veterinario):
    animal = animal_do_veterinario(db, id, uid)
    db.delete(animal)
    db.commit()
