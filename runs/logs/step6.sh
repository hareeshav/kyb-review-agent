#!/bin/zsh
set -e
cd /Users/hareeshveduraj/AICohort/Project/kyb-review-agent
PY=.venv/bin/python
L=runs/logs
$PY -m kyb.cli run all --runs 3 > $L/run_all.out 2> $L/run_all.err; echo "run all done"
$PY -m kyb.cli eval > $L/eval.out 2>&1; echo "eval done"
for a in A B C; do $PY -m kyb.cli judge $a > $L/judge_$a.out 2> $L/judge_$a.err; echo "judge $a done"; done
$PY -m kyb.cli adversarial C > $L/adversarial_C.out 2> $L/adversarial_C.err; echo "adversarial done"
