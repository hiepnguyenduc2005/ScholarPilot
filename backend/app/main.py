# import os
# from fastapi import FastAPI
# import uvicorn
# from api import endpoints  # Ensure your endpoints are defined in this module.
# import modal
# from dotenv import load_dotenv

# load_dotenv()
# os.environ["TOKENIZERS_PARALLELISM"] = "false"

# # Check an environment variable to decide if we are in deployment mode.
# # Set MODAL_DEPLOY=true when deploying on Modal.
# if os.environ.get("MODAL_DEPLOY", "").lower() == "true":
#     # Deployment mode: Build the image from requirements.txt.
#     req_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "requirements.txt")
#     with open(req_path) as f:
#         requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
#     image = (
#         modal.Image.debian_slim()
#         .pip_install(*requirements)
#     )
# else:
#     # For local development, we assume the dependencies are already installed
#     # and we don't need to build a Modal image.
#     image = None

# def create_app() -> FastAPI:
#     web_app = FastAPI(title="ScholarPilot")
#     web_app.include_router(endpoints.router, prefix="/api")
#     return web_app

# app = modal.App("scholar-pilot", image=image)

# @app.function(secrets=[modal.Secret.from_name("devfest")])
# @modal.web_endpoint()
# def fastapi_app():
#     return create_app()

# @app.local_entrypoint()
# def local_run():
#     uvicorn.run("main:create_app", host="0.0.0.0", port=8000, reload=True)

# if __name__ == "__main__":
#     local_run()

from fastapi import FastAPI
import uvicorn
from api import endpoints
import os

app = FastAPI(title="ScholarPilot")
app.include_router(endpoints.router, prefix="/api")

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)