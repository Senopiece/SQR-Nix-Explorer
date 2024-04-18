from fastapi import APIRouter, HTTPException

from back.api.dependencies import CurrentUserDep, NixDep, DBDep
from back.api.errors import ErrorResponse
from back.api.services.store import get_store_for_interactions
from back.db.models import UserStore
from back.db.repository import DBException

store_router = APIRouter(
    prefix="/store",
    tags=["Store"],
    responses={
        400: {"model": ErrorResponse, "description": "Error during request"},
        401: {"model": ErrorResponse, "description": "Auth error"},
    },
)


@store_router.post("", response_model=UserStore, status_code=201)
def add_store(store_name: str, user: CurrentUserDep, nix: NixDep, db: DBDep):
    if db.get_store(store_name) is not None:
        raise DBException(f"Store {store_name} already exists")

    store_id = nix.add_store(store_name)
    store = db.create_store(user, store_name, store_id)

    return store


@store_router.delete("", status_code=204)
def remove_store(store_name: str, user: CurrentUserDep, nix: NixDep, db: DBDep):
    store = get_store_for_interactions(store_name, db, user)

    nix.remove_store(store.id)
    db.remove_store(store.id)


@store_router.post("/store/package", status_code=201)
def add_package_to_store(
    store_name: str, package_name: str, user: CurrentUserDep, nix: NixDep, db: DBDep
):
    store = get_store_for_interactions(store_name, db, user)

    nix.add_package_to_store(store.id, package_name)


@store_router.delete("/store/package", status_code=204)
def remove_package_from_store(
    store_name: str, package_name: str, user: CurrentUserDep, nix: NixDep, db: DBDep
):
    store = get_store_for_interactions(store_name, db, user)

    nix.remove_package_from_store(store.id, package_name)


@store_router.get("/store/check_package_exists")
def check_package_exists(
    store_name: str, package_name: str, user: CurrentUserDep, nix: NixDep, db: DBDep
):
    store = get_store_for_interactions(store_name, db, user)

    return nix.check_package_exists(store.id, package_name)


@store_router.get("/store/get_difference_paths", response_model=list[str])
def get_difference_of_paths(
    store_name1: str, store_name2: str, user: CurrentUserDep, nix: NixDep, db: DBDep
):
    store1 = get_store_for_interactions(store_name1, db, user)
    store2 = get_store_for_interactions(store_name2, db, user)

    return nix.get_difference_of_paths(store1.id, store2.id)


@store_router.get("/store/get_difference_paths")
def get_difference_of_package_closures(
    package1: str, package2: str, user: CurrentUserDep, nix: NixDep, db: DBDep
):
    # Where I should get stores? All user stores?
    # ex: store1#bash,  store2#hello
    raise HTTPException(status_code=500, detail="Not implemented")