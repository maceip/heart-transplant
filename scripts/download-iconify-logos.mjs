import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, '..');
const outDir = path.join(root, 'frontend', 'public', 'vendor-icons', 'logos');
const apiBase = 'https://api.iconify.design';
const collectionUrl = `${apiBase}/collection?prefix=logos&info=1`;
const concurrency = 20;

const collection = await fetchJson(collectionUrl);
const iconNames = getVisibleIcons(collection);

await mkdir(outDir, { recursive: true });

const manifest = {
  prefix: collection.prefix,
  title: collection.title,
  totalVisibleIcons: iconNames.length,
  fetchedAt: new Date().toISOString(),
  sourcePage: 'https://icon-sets.iconify.design/logos/',
  apiCollection: collectionUrl,
  license: collection.info?.license ?? null,
  author: collection.info?.author ?? null,
  icons: iconNames,
};

await writeFile(
  path.join(outDir, 'manifest.json'),
  JSON.stringify(manifest, null, 2),
  'utf8',
);

await downloadAll(iconNames, concurrency);

console.log(`Downloaded ${iconNames.length} SVG files to ${outDir}`);

async function downloadAll(names, limit) {
  let index = 0;
  let completed = 0;

  const workers = Array.from({ length: Math.min(limit, names.length) }, async () => {
    while (index < names.length) {
      const current = names[index++];
      const svgUrl = `${apiBase}/logos/${encodeURIComponent(current)}.svg?height=none`;
      const response = await fetch(svgUrl);
      if (!response.ok) {
        throw new Error(`Failed to download ${current}: ${response.status} ${response.statusText}`);
      }
      const svg = await response.text();
      await writeFile(path.join(outDir, `${current}.svg`), svg, 'utf8');
      completed += 1;
      if (completed % 100 === 0 || completed === names.length) {
        console.log(`Downloaded ${completed}/${names.length}`);
      }
    }
  });

  await Promise.all(workers);
}

function getVisibleIcons(collection) {
  const names = new Set();

  for (const iconName of collection.uncategorized ?? []) {
    names.add(iconName);
  }

  for (const icons of Object.values(collection.categories ?? {})) {
    for (const iconName of icons) {
      names.add(iconName);
    }
  }

  return [...names].sort();
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`);
  }
  return response.json();
}
