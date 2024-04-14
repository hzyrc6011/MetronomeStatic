# MetronomeStatic
<svg t="1712932897209" class="icon" viewBox="0 0 1024 1024" version="1.1" xmlns="http://www.w3.org/2000/svg" p-id="4262" width="200" height="200"><path d="M512 74.666667l-146.346667 39.253333-192.426666 719.36c-1.28 6.4-2.56 13.226667-2.56 20.053333 0 47.36 37.973333 85.333333 85.333333 85.333334h512c47.36 0 85.333333-37.973333 85.333333-85.333334 0-6.826667-1.28-13.653333-2.56-20.053333l-58.026666-218.026667L725.333333 682.666667l8.533334 42.666666h-161.706667l121.173333-121.173333-60.16-60.16L451.84 725.333333H290.133333l148.906667-554.666666h145.92l62.293333 231.68 69.546667-69.973334-58.453333-218.453333L512 74.666667M480 213.333333v416l64-64V213.333333h-64m364.373333 119.466667l-120.746666 120.746667-30.293334-30.293334-60.16 60.586667 120.32 120.32 60.586667-60.16-30.293333-30.293333 120.746666-120.746667-60.16-60.16z" p-id="4263" fill="#1296db"></path></svg>
[![Document-Build](https://github.com/hzyrc6011/MetronomeStatic/actions/workflows/pages/pages-build-deployment/badge.svg)](https://github.com/hzyrc6011/MetronomeStatic/actions/workflows/pages/pages-build-deployment)

A pure-python (Python>=3.8) static analysis library providing various interfaces.

For detailed informations, please visit this webpage:
[Documentation Website](https://hzyrc6011.github.io/MetronomeStatic/)

## Installation

```bash
pip install MetronomeStatic
```

If you would like to run it in jupyter, please install jupyter by the commands below:

```bash
pip install jupyterlab ipywidgets
```

## Interfaces

### Clang

Clang interface included some useful functionalities.

## Microservice By MessageQueue

### Task dispatch procedure

- `TaskQueue` and `ResultQueue` are `queue.Queue`s in the server program.
- `Get Task` and `Push Result` procedures are performed by RESTFUL API.

```mermaid
sequenceDiagram

participant s as Server
participant tmq as TaskQueue
participant rmq as ResultQueue
participant t1 as Tool1
participant t2 as Tool2

s ->> tmq: Put task 
tmq ->> t1: Get task
t1 ->> t1: handle task
tmq ->> s: Count remaining tasks
tmq ->> t2: Get task
t2 ->> t2: handle task
tmq ->> s: Count remaining tasks
t2 ->> rmq: Push result
t1 ->> rmq: Push result
rmq ->> s: Listen to result messages
```

### Status pushing procedure

- A background task running in each tool and pushing the status of tools to scheduler by
`Websocket` every second.

### Autocompletion Request

```mermaid
sequenceDiagram

participant s as Server
participant q as TmpQueue
participant st as WSRecvThread
participant t as Tool

s -x q: Create Tmp Queue
s ->>+ t: WS Request No.145
activate s
s -->> s: Blocking get() from TmpQueue
t -->> t: Compute the autocompletion items

t -->>- st: WS Reply No.145
activate st
st ->> st: Match WS Req/Rep by No.
st -->>+ q: Put reply
deactivate st
q -->>- s: q.get() resolved and got the reply
deactivate s
s --x q: destroy the TmpQueue
```

## In-Repo Third Party Dependencies

### [PyC-CFG](https://github.com/shramos/pyc-cfg)

Pyc-cfg is a pure python control flow graph builder for almost all Ansi C programming language.

As the original version only suitable for Python2, I copied its code and made it compatible for python 3.
