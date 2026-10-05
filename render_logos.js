// Renders the nfl-team-logos React components to plain SVG files in build/logos/.
// A file you drop in logos/ (e.g. logos/TEN.svg or logos/TEN.png) always wins over the package.
const React=require('react');const {renderToStaticMarkup}=require('react-dom/server');
const fs=require('fs');const path=require('path');
const out=path.join(__dirname,'..','build','logos');fs.mkdirSync(out,{recursive:true});
const dir=path.dirname(require.resolve('nfl-team-logos/package.json'))+'/dist/logos/';
let n=0;
for(const f of fs.readdirSync(dir).filter(x=>x.endsWith('.js'))){
  const m=require(dir+f);const C=m.default||Object.values(m)[0];
  let s=renderToStaticMarkup(React.createElement(C,{}));
  if(!s.slice(0,200).includes('xmlns='))s=s.replace('<svg','<svg xmlns="http://www.w3.org/2000/svg"');
  fs.writeFileSync(path.join(out,f.replace('.js','.svg')),s);n++;
}
console.log('rendered',n,'logos');
