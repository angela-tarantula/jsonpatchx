# Getting Started

This page gets you from install to a working patch contract quickly. The
examples here are short verification snippets you can run immediately.

## Install

Core package:

```sh
pip install jsonpatchx
```

Optional FastAPI helpers (`JsonPatchRoute`, error mapping):

```sh
pip install "jsonpatchx[fastapi]"
```

`JsonPatchFor` is in the core package.

## Example 1: Parse Once, Apply Many

```python
from jsonpatchx import JsonPatch

patch = JsonPatch(
    [
        {"op": "replace", "path": "/name", "value": "Ada Lovelace"},
        {"op": "add", "path": "/tags/-", "value": "priority"},
    ]
)

doc_a = {"name": "Ada", "tags": ["vip"]}
doc_b = {"name": "A. Byron", "tags": []}

updated_a = patch.apply(doc_a)
updated_b = patch.apply(doc_b)
```

## Example 2: FastAPI PATCH Contract

```python
from fastapi import FastAPI
from pydantic import BaseModel

from jsonpatchx import StandardRegistry
from jsonpatchx.pydantic import JsonPatchFor


class User(BaseModel):
    id: int
    name: str


UserPatch = JsonPatchFor[User, StandardRegistry]
app = FastAPI()


@app.patch("/users/{user_id}", response_model=User)
def patch_user(user_id: int, patch: UserPatch) -> User:
    user = load_user(user_id)
    updated = patch.apply(user)
    save_user(user_id, updated)
    return updated
```

OpenAPI produced by this route:

```json
{
  "components": {
    "schemas": {
      "HTTPValidationError": {
        "properties": {
          "detail": {
            "items": {
              "$ref": "#/components/schemas/ValidationError"
            },
            "title": "Detail",
            "type": "array"
          }
        },
        "title": "HTTPValidationError",
        "type": "object"
      },
      "User": {
        "properties": {
          "id": {
            "title": "Id",
            "type": "integer"
          },
          "name": {
            "title": "Name",
            "type": "string"
          }
        },
        "required": ["id", "name"],
        "title": "User",
        "type": "object"
      },
      "UserPatchOperation": {
        "description": "Discriminated union of patch operations for User.",
        "discriminator": {
          "mapping": {
            "add": "#/components/schemas/AddOp",
            "copy": "#/components/schemas/CopyOp",
            "move": "#/components/schemas/MoveOp",
            "remove": "#/components/schemas/RemoveOp",
            "replace": "#/components/schemas/ReplaceOp",
            "test": "#/components/schemas/TestOp"
          },
          "propertyName": "op"
        },
        "oneOf": [
          {
            "$ref": "#/components/schemas/AddOp"
          },
          {
            "$ref": "#/components/schemas/CopyOp"
          },
          {
            "$ref": "#/components/schemas/MoveOp"
          },
          {
            "$ref": "#/components/schemas/RemoveOp"
          },
          {
            "$ref": "#/components/schemas/ReplaceOp"
          },
          {
            "$ref": "#/components/schemas/TestOp"
          }
        ],
        "title": "User Patch Operation"
      },
      "UserPatchRequest": {
        "description": "Array of patch operations for User. Applied to model_dump() and re-validated against the model schema.",
        "items": {
          "$ref": "#/components/schemas/UserPatchOperation"
        },
        "title": "User Patch Request",
        "type": "array",
        "x-target-model": "User"
      },
      "ValidationError": {
        "properties": {
          "ctx": {
            "title": "Context",
            "type": "object"
          },
          "input": {
            "title": "Input"
          },
          "loc": {
            "items": {
              "anyOf": [
                {
                  "type": "string"
                },
                {
                  "type": "integer"
                }
              ]
            },
            "title": "Location",
            "type": "array"
          },
          "msg": {
            "title": "Message",
            "type": "string"
          },
          "type": {
            "title": "Error Type",
            "type": "string"
          }
        },
        "required": ["loc", "msg", "type"],
        "title": "ValidationError",
        "type": "object"
      }
    }
  },
  "paths": {
    "/users/{user_id}": {
      "patch": {
        "operationId": "patch_user_users__user_id__patch",
        "parameters": [
          {
            "in": "path",
            "name": "user_id",
            "required": true,
            "schema": {
              "title": "User Id",
              "type": "integer"
            }
          }
        ],
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "$ref": "#/components/schemas/UserPatchRequest"
              }
            }
          },
          "required": true
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/User"
                }
              }
            },
            "description": "Successful Response"
          },
          "422": {
            "content": {
              "application/json": {
                "schema": {
                  "$ref": "#/components/schemas/HTTPValidationError"
                }
              }
            },
            "description": "Validation Error"
          }
        },
        "summary": "Patch User"
      }
    }
  }
}
```

## Continue

- Plain JSON runtime usage: [Patching Plain JSON](patching-plain-json.md)
- Contract-first FastAPI setup: [FastAPI Integration](fastapi-integration.md)
- PATCH vocabulary control: [Operation Registries](operation-registries.md)
