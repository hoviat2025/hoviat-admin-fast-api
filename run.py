"""Run the local API with: python run.py."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=18743, reload=True)
