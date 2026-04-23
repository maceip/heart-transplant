import { createHash } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

const ROOT = path.join(process.cwd(), '.repocity', 'ingests');

export async function createArtifactWorkspace(repoMeta, archiveBuffer, files) {
  const artifactId = buildArtifactId(repoMeta.fullName, repoMeta.defaultBranch, archiveBuffer);
  const dir = path.join(ROOT, artifactId);
  const filesDir = path.join(dir, 'files');

  await mkdir(filesDir, { recursive: true });
  await writeFile(path.join(dir, 'archive.zip'), archiveBuffer);

  for (const [filePath, content] of files.entries()) {
    const target = path.join(filesDir, ...filePath.split('/'));
    await mkdir(path.dirname(target), { recursive: true });
    await writeFile(target, content, 'utf8');
  }

  return {
    artifactId,
    dir,
    filesDir,
    relativeDir: path.relative(process.cwd(), dir),
  };
}

export async function writeArtifactJson(dir, name, value) {
  await writeFile(path.join(dir, name), JSON.stringify(value, null, 2), 'utf8');
}

function buildArtifactId(fullName, branch, archiveBuffer) {
  const stamp = new Date().toISOString().replace(/[:.]/g, '-');
  const repoSlug = fullName.replace(/[^\w.-]+/g, '_');
  const digest = createHash('sha1').update(archiveBuffer).digest('hex').slice(0, 12);
  return `${stamp}__${repoSlug}__${branch}__${digest}`;
}
