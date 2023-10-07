# Sisyphus Client

## Introduction

The `sisyphus-client` is the worker client for the Sisyphus distributed encoding system.  It's responsible for polling the server queue for jobs, processing those jobs, and generally doing all of the hard work.

Jobs are simply a set of tasks with each task calling a Sisyphus module to accomplish specific things.  Currently, the default modules that can be used are:

- `ffmpeg`: A Ffmpeg module that uses `ffmpeg` to encode various sources.
- `mkvmerge`: A Matroska muxing module that can be used to mux one or more source files together.
- `mkvextract`: A Matroska module that can extract a myriad of things to include streams, chapter information, and tag information.
- `cleanup`: A cleanup module used to cleanup any temporary files left over from the job, or to move/copy files from one location or the other.

For more information on Sisyphus (and the `sisyphus-client`), you can [read the documentation here](https://sisyphus.jamesthebard.net).

## Quick Start

### Prerequisites

- `docker` installed
- The Sisyphus API server installed

### Procedure

1. Clone the `sisyphus-client` repository.

    ```bash
    git clone https://github.com/JamesTheBard/sisyphus-client
    ```

2. Navigate to the `docker` directory.

    ```bash
    cd sisyphus-client/docker
    ```

3. Run the Docker Compose file in the directory.

    ```bash
    export API_URL="http://api.server.url.here:5000"
    export HOST_UUID="00000000-1111-2222-3333-444444444444"
    docker compose up -d
    ```

4. Verify that the container has started successfully by querying the API server for available workers.  The new worker should appear in the `/workers` list.

    ```bash
    curl -X GET http://api.server.url.here:5000/workers
    ```

    ```json
    {
      "workers": [
        {
          "status": "idle",
          "hostname": "encode001",
          "version": "1.3.4",
          "online_at": "2023-10-02 16:39:02.714402+00:00",
          "worker_id": "00000000-1111-2222-3333-444444444444",
          "attributes": {
            "disabled": false
          }
        }
      ],
      "count": 1
    }
    ```