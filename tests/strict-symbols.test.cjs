'use strict';
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');

const yaml=fs.readFileSync(path.join(__dirname,'..','Oreslang.sublime-syntax'),'utf8');
const line=yaml.split(/\r?\n/).find(x=>x.trim().startsWith("- match: '#(?:"));
assert.ok(line,"must define a Symbol literal grammar rule");
const source=line.trim().match(/^- match: '((?:''|[^'])*)'$/);
assert.ok(source,"expected YAML-escaped single-quoted Symbol rule");
const grammar=source[1].replace(/''/g,"'");
const regex=new RegExp('^(?:'+grammar+')$');

test('Sublime grammar scopes exact valid Symbol literal boundaries',()=>{
  for(const value of [
    '#ready', "#'with spaces'", '#"quoted value"',
    String.raw`#"\u0061"`,
    String.raw`#"escaped \" quote"`,
    '#'+ 'a'.repeat(128)
  ]) assert.equal(regex.test(value),true,value);
});

test('Sublime grammar refuses invalid and overlong Symbol tokens',()=>{
  for(const value of [
    '#', '# ready', '#123', "#''", '#""',
    '#'+ 'a'.repeat(129),
    String.raw`#"bad\q"`,
    String.raw`#"bad\n"`,
    String.raw`#"bad\uZZZZ"`,
    '#"raw\nnewline"', "#'raw\rnewline'",
    '#"unterminated'
  ]) assert.equal(regex.test(value),false,value);
});

test('Sublime keyword pattern cannot reinterpret malformed symbols as valid symbols',()=>{
  assert.equal(regex.test('#'+'m'.repeat(200)),false);
  assert.ok(yaml.indexOf('push: block-comment')>=0);
  assert.ok(yaml.indexOf('meta_scope: string.quoted.template.oreslang')>=0);
});
