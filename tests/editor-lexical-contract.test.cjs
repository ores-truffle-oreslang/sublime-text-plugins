'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');

const raw = fs.readFileSync(path.join(__dirname,'../contracts/editor-syntax/v1/editor-lexical-contract.json'));
const manifest = JSON.parse(raw.toString('utf8'));
const SHA='e9dbf3b6fad5562b7ca6df631ab3c45f478480ba';
const gitBlob=crypto.createHash('sha1').update('blob '+raw.length+'\0').update(raw).digest('hex');
const yaml=fs.readFileSync(path.join(__dirname,'../Oreslang.sublime-syntax'),'utf8');

function yamlSingleQuoted(line) {
  const hit=line.match(/:\s*'((?:''|[^'])*)'\s*$/);
  if(!hit) throw new Error('expected YAML single-quoted regex: '+line);
  return hit[1].replace(/''/g,"'");
}
const lines=yaml.split(/\r?\n/);
const variable=name=>new RegExp(yamlSingleQuoted(lines.find(line=>line.startsWith('  '+name+': '))));
const keywords=variable('keywords');
const globals=variable('global_controls');
const comparisons=new RegExp(yamlSingleQuoted(lines.find(line=>line.includes("scope: keyword.operator.comparison.oreslang") ? false : line.trim().startsWith("- match:") && line.includes("eq|neq|is"))));
const compound=new RegExp(yamlSingleQuoted(lines.find(line=>line.includes('critical-read|critical-write|nb-select|transform-pipe'))));
const symbolLine=lines.find(line=>line.trim().startsWith("- match: '#(?:"));
const symbol=new RegExp(yamlSingleQuoted(symbolLine).replace('{{identifier}}','[A-Za-z_][A-Za-z0-9_]*'));
const operatorLine=lines.find(line=>line.includes('[+\\-*/%=&|^~!<>?:]'));
if(!operatorLine) throw new Error('missing percent/caret lexer token scopes');
const operators=new RegExp(yamlSingleQuoted(operatorLine));

test('Sublime syntax pins the exact common-source Git blob',()=>{
  assert.equal(gitBlob,SHA);
  assert.equal(manifest.version,1);
  assert.match(manifest.status,/NOT parser or backend acceptance/);
});
for(const fixture of manifest.fixtures) {
  test('Sublime static-scope fixture: '+fixture.id,()=>{
    for(const token of fixture.expected) {
      if(token.kind==='keyword') {
        assert.ok(compound.test(token.value)||keywords.test(token.value),fixture.id+': '+token.value);
      } else if(token.kind==='runtimeGlobal') {
        assert.ok(globals.test(token.value),fixture.id+': '+token.value);
      } else if(token.kind==='operator') {
        assert.ok(comparisons.test(token.value)||operators.test(token.value),fixture.id+': '+token.value);
      } else if(token.kind==='symbol') {
        assert.equal(token.value.match(symbol)?.[0],token.value,fixture.id+': '+token.value);
      } else if(token.kind==='plain') {
        assert.ok(!keywords.test(token.value)&&!comparisons.test(token.value),fixture.id+': '+token.value);
      }
    }
    if(fixture.id==='opaque-comments-strings') {
      assert.ok(yaml.includes('push: block-comment'));
      assert.ok(yaml.includes('string.quoted.template.oreslang'));
    }
  });
}

test('all 93 compiler lexer-reserved words have a grammar recognition rule',()=>{
  for(const word of manifest.reservedWords) {
    const recognized=keywords.test(word)||globals.test(word)||comparisons.test(word);
    assert.ok(recognized,'missing pinned Java lexer token: '+word);
  }
});
