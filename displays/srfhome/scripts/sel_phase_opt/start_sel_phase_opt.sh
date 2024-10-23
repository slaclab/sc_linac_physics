#!/bin/bash

export TMUX_SSH_USER=laci
export TMUX_SSH_SERVER=lcls-srv03
tmux_launcher restart /home/physics/srf/gitRepos/sel_phase_opt/launch.sh sel_phase_opt