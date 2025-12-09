#!/bin/bash

docker stop lightspeed
sudo rm -rf ../harness/tools/docker/data
docker start lightspeed