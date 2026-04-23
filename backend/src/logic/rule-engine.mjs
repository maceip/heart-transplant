export function createFactStore(seedFacts = []) {
  const store = new Map();
  for (const fact of seedFacts) {
    addFact(store, fact);
  }
  return store;
}

export function runRules(seedFacts, rules, options = {}) {
  const store = createFactStore(seedFacts);
  const maxIterations = options.maxIterations ?? 50;

  for (let iteration = 0; iteration < maxIterations; iteration += 1) {
    let changed = false;

    for (const rule of rules) {
      const bindings = evaluateBody(store, rule.body);
      for (const binding of bindings) {
        const fact = instantiateHead(rule.head, binding);
        changed = addFact(store, fact) || changed;
      }
    }

    if (!changed) {
      break;
    }
  }

  return flattenStore(store);
}

export function queryFacts(facts, predicate) {
  return facts.filter((fact) => fact.predicate === predicate);
}

function evaluateBody(store, atoms) {
  let bindings = [{}];

  for (const atom of atoms) {
    if (atom.type === 'not') {
      bindings = bindings.filter((binding) => !hasMatchingFact(store, atom.atom, binding));
      continue;
    }

    const facts = store.get(atom.predicate) ?? [];
    const nextBindings = [];

    for (const binding of bindings) {
      for (const fact of facts) {
        const unified = unify(binding, atom.args, fact.args);
        if (unified) {
          nextBindings.push(unified);
        }
      }
    }

    bindings = dedupeBindings(nextBindings);
    if (!bindings.length) {
      break;
    }
  }

  return bindings;
}

function hasMatchingFact(store, atom, binding) {
  const facts = store.get(atom.predicate) ?? [];
  return facts.some((fact) => Boolean(unify(binding, atom.args, fact.args)));
}

function unify(binding, patternArgs, factArgs) {
  if (patternArgs.length !== factArgs.length) {
    return null;
  }

  const next = { ...binding };

  for (let index = 0; index < patternArgs.length; index += 1) {
    const pattern = patternArgs[index];
    const value = factArgs[index];

    if (isVariable(pattern)) {
      const existing = next[pattern];
      if (existing !== undefined && existing !== value) {
        return null;
      }
      next[pattern] = value;
      continue;
    }

    if (pattern !== value) {
      return null;
    }
  }

  return next;
}

function instantiateHead(head, binding) {
  return {
    predicate: head.predicate,
    args: head.args.map((arg) => (isVariable(arg) ? binding[arg] : arg)),
  };
}

function addFact(store, fact) {
  const key = factKey(fact);
  const bucket = store.get(fact.predicate) ?? [];
  if (bucket.some((candidate) => factKey(candidate) === key)) {
    return false;
  }
  bucket.push(fact);
  store.set(fact.predicate, bucket);
  return true;
}

function flattenStore(store) {
  return [...store.values()].flatMap((facts) => facts);
}

function factKey(fact) {
  return `${fact.predicate}::${fact.args.map((arg) => JSON.stringify(arg)).join('|')}`;
}

function dedupeBindings(bindings) {
  const seen = new Set();
  return bindings.filter((binding) => {
    const key = JSON.stringify(binding, Object.keys(binding).sort());
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}

function isVariable(value) {
  return typeof value === 'string' && value.startsWith('?');
}
