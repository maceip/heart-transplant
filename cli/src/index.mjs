#!/usr/bin/env node

const args = process.argv.slice(2);

if (args.includes('--help') || args.includes('-h')) {
  console.log('heart-transplant CLI scaffold');
  console.log('');
  console.log('Planned commands:');
  console.log('  ingest <repo>');
  console.log('  scan <repo>');
  console.log('  migrate <repo> --from <vendor> --to <vendor>');
  process.exit(0);
}

console.log('heart-transplant CLI scaffold ready');
