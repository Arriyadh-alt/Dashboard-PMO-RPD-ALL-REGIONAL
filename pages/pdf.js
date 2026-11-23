/* Text-only, paginated PDFs; never interpret report cells as HTML or images. */
(() => {
  // Built-in Helvetica is WinAnsi, not a Unicode font. Never let one unsupported
  // glyph switch an entire line into unreadable UTF-16 bytes. Preserve a visible
  // code-point notation instead; CSV/XLSX retain the verbatim source text.
  const winAnsi=new Set('€‚ƒ„…†‡ˆ‰Š‹ŒŽ‘’“”•–—˜™š›œžŸ');
  function pdfText(value){return Array.from(String(value),char=>{const cp=char.codePointAt(0);return cp===10||cp===13||(cp>=32&&cp<=126)||(cp>=160&&cp<=255)||winAnsi.has(char)?char:'\\u{'+cp.toString(16).toUpperCase()+'}'}).join('')}
  function renderPDF(model,jsPDF,autoTable){
    let escaped=false;
    const plain=value=>{const original=value==null?'Insufficient Data':String(value),safe=pdfText(original);if(safe!==original)escaped=true;return safe};
    const metadata=model.metadata.map(plain),headers=model.headers.map(plain),rows=model.rows.map(row=>row.map(plain));
    if(escaped)metadata.push('Karakter di luar font PDF ditulis sebagai \\u{HEX}; gunakan CSV/XLSX untuk teks asli.');
    const doc=new jsPDF({orientation:'landscape',unit:'mm',format:'a4',compress:true}),margin=12,width=doc.internal.pageSize.getWidth(),height=doc.internal.pageSize.getHeight();
    let y=margin;
    doc.setFont('helvetica','bold');doc.setFontSize(16);
    for(const line of doc.splitTextToSize(metadata[0],width-margin*2)){doc.text(line,margin,y);y+=7}
    doc.setFont('helvetica','normal');doc.setFontSize(8);
    for(const item of metadata.slice(1)){
      for(const line of doc.splitTextToSize(String(item),width-margin*2)){
        if(y>height-20){doc.addPage();y=margin}
        doc.text(line,margin,y);y+=4;
      }
      y+=1;
    }
    autoTable(doc,{head:[headers],body:rows,startY:y+3,margin:{top:margin,left:margin,right:margin,bottom:15},showHead:'everyPage',rowPageBreak:'auto',styles:{font:'helvetica',fontSize:7,cellPadding:1.5,overflow:'linebreak',lineWidth:.1,lineColor:[222,229,237]},headStyles:{fillColor:[20,43,73],textColor:[255,255,255]},alternateRowStyles:{fillColor:[245,248,251]}});
    for(let page=1;page<=doc.getNumberOfPages();page++){doc.setPage(page);doc.setFontSize(8);doc.text('PMO RPD | Page '+page,width-margin,height-6,{align:'right'})}
    return new Uint8Array(doc.output('arraybuffer'));
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={renderPDF};else window.RPDPDF=Object.freeze({renderPDF});
})();
