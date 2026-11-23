/* Text-only, paginated PDFs; never interpret report cells as HTML or images. */
(() => {
  function renderPDF(model,jsPDF,autoTable){
    const doc=new jsPDF({orientation:'landscape',unit:'mm',format:'a4',compress:true}),margin=12,width=doc.internal.pageSize.getWidth(),height=doc.internal.pageSize.getHeight();
    let y=margin;
    doc.setFont('helvetica','bold');doc.setFontSize(16);
    for(const line of doc.splitTextToSize(String(model.metadata[0]),width-margin*2)){doc.text(line,margin,y);y+=7}
    doc.setFont('helvetica','normal');doc.setFontSize(8);
    for(const item of model.metadata.slice(1)){
      for(const line of doc.splitTextToSize(String(item),width-margin*2)){
        if(y>height-20){doc.addPage();y=margin}
        doc.text(line,margin,y);y+=4;
      }
      y+=1;
    }
    autoTable(doc,{head:[model.headers],body:model.rows.map(row=>row.map(value=>value==null?'Insufficient Data':String(value))),startY:y+3,margin:{top:margin,left:margin,right:margin,bottom:15},showHead:'everyPage',rowPageBreak:'auto',styles:{font:'helvetica',fontSize:7,cellPadding:1.5,overflow:'linebreak',lineWidth:.1,lineColor:[222,229,237]},headStyles:{fillColor:[20,43,73],textColor:[255,255,255]},alternateRowStyles:{fillColor:[245,248,251]}});
    for(let page=1;page<=doc.getNumberOfPages();page++){doc.setPage(page);doc.setFontSize(8);doc.text('PMO RPD | Page '+page,width-margin,height-6,{align:'right'})}
    return new Uint8Array(doc.output('arraybuffer'));
  }
  if(typeof module!=='undefined'&&module.exports)module.exports={renderPDF};else window.RPDPDF=Object.freeze({renderPDF});
})();
