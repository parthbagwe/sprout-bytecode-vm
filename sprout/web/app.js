const samples = {
  fibonacci: `// Recursion and call frames
fn fib(n) {
  if n < 2 {
    return n;
  }
  return fib(n - 1) + fib(n - 2);
}

let i = 0;
while i < 10 {
  print fib(i);
  i = i + 1;
}`,

  controlFlow: `// Variables, loops, and branching
let total = 0;
let n = 1;

while n <= 8 {
  if n == 5 {
    print "halfway";
  }
  total = total + n;
  n = n + 1;
}

print "sum:";
print total;`,

  functions: `// Functions, locals, and strings
fn describe(name, score) {
  let label = " is learning the VM";
  if score >= 90 {
    label = " mastered bytecode";
  }
  return name + label;
}

print describe("Sprout", 95);`,

  error: `// Runtime errors include a source stack trace
fn divide(a, b) {
  return a / b;
}

fn calculate() {
  return divide(42, 0);
}

print calculate();`,
};

const editor = document.querySelector("#source-editor");
const lineNumbers = document.querySelector("#line-numbers");
const cursorPosition = document.querySelector("#cursor-position");
const characterCount = document.querySelector("#character-count");
const sampleSelect = document.querySelector("#sample-select");
const loadSampleButton = document.querySelector("#load-sample");
const runButton = document.querySelector("#run-button");
const traceToggle = document.querySelector("#trace-toggle");
const status = document.querySelector("#server-status");
const resultState = document.querySelector("#result-state");
const emptyState = document.querySelector("#empty-state");
const outputPanel = document.querySelector("#panel-output");
const bytecodePanel = document.querySelector("#panel-bytecode");
const tracePanel = document.querySelector("#panel-trace");
const statCompiled = document.querySelector("#stat-compiled");
const statExecuted = document.querySelector("#stat-executed");
const statTime = document.querySelector("#stat-time");
const tabs = [...document.querySelectorAll(".tab")];

function setSource(source) {
  editor.value = source;
  updateEditorMeta();
  localStorage.setItem("sprout-source", source);
}

function updateEditorMeta() {
  const lines = editor.value.split("\n");
  lineNumbers.textContent = lines.map((_, index) => index + 1).join("\n");
  characterCount.textContent = `${editor.value.length} chars`;

  const beforeCursor = editor.value.slice(0, editor.selectionStart);
  const currentLine = beforeCursor.split("\n");
  cursorPosition.textContent = `Ln ${currentLine.length}, Col ${currentLine.at(-1).length + 1}`;
}

function selectTab(name) {
  tabs.forEach((tab) => {
    const active = tab.dataset.panel === name;
    tab.classList.toggle("active", active);
    tab.setAttribute("aria-selected", String(active));
  });

  [outputPanel, bytecodePanel, tracePanel].forEach((panel) => {
    const active = panel.id === `panel-${name}`;
    panel.classList.toggle("active", active);
    panel.hidden = !active;
  });
}

function setBusy(busy) {
  runButton.disabled = busy;
  status.className = busy ? "status-pill busy" : "status-pill";
  status.lastChild.textContent = busy ? " Compiling…" : " VM ready";
  runButton.querySelector(".run-label").textContent = busy ? "Running…" : "Compile & run";
}

async function runProgram() {
  setBusy(true);
  emptyState.classList.add("hidden");
  outputPanel.classList.remove("error");
  resultState.className = "result-state";
  resultState.textContent = "Running";

  try {
    const response = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: editor.value, trace: traceToggle.checked }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `Server returned ${response.status}`);
    }

    outputPanel.textContent = data.ok
      ? (data.output || "Program completed without output.")
      : `Sprout error\n────────────\n${data.error}${data.output ? `\n\nOutput before error:\n${data.output}` : ""}`;
    outputPanel.classList.toggle("error", !data.ok);
    bytecodePanel.textContent = data.bytecode || "No bytecode was generated.";
    tracePanel.textContent = traceToggle.checked
      ? (data.trace || "No VM instructions were traced.")
      : "Enable ‘Trace VM’, then run the program to inspect every stack transition.";

    statCompiled.textContent = data.stats.compiledInstructions.toLocaleString();
    statExecuted.textContent = data.stats.executedInstructions.toLocaleString();
    statTime.textContent = data.stats.elapsedMs.toLocaleString();
    resultState.textContent = data.ok ? "Success" : "Error";
    resultState.className = `result-state ${data.ok ? "success" : "failure"}`;
    selectTab("output");
  } catch (error) {
    outputPanel.textContent = `Could not reach the local Sprout server.\n\n${error.message}`;
    outputPanel.classList.add("error");
    resultState.textContent = "Offline";
    resultState.className = "result-state failure";
    status.className = "status-pill error";
    status.lastChild.textContent = " Server offline";
    selectTab("output");
  } finally {
    runButton.disabled = false;
    runButton.querySelector(".run-label").textContent = "Compile & run";
    if (!status.classList.contains("error")) {
      setBusy(false);
    }
  }
}

editor.addEventListener("input", () => {
  updateEditorMeta();
  localStorage.setItem("sprout-source", editor.value);
});

editor.addEventListener("click", updateEditorMeta);
editor.addEventListener("keyup", updateEditorMeta);
editor.addEventListener("scroll", () => {
  lineNumbers.scrollTop = editor.scrollTop;
});

editor.addEventListener("keydown", (event) => {
  if (event.key === "Tab") {
    event.preventDefault();
    const start = editor.selectionStart;
    const end = editor.selectionEnd;
    editor.setRangeText("  ", start, end, "end");
    editor.dispatchEvent(new Event("input"));
  }
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
    event.preventDefault();
    runProgram();
  }
});

loadSampleButton.addEventListener("click", () => {
  setSource(samples[sampleSelect.value]);
  editor.focus();
});

runButton.addEventListener("click", runProgram);

tabs.forEach((tab) => {
  tab.addEventListener("click", () => selectTab(tab.dataset.panel));
});

const savedSource = localStorage.getItem("sprout-source");
setSource(savedSource || samples.fibonacci);

