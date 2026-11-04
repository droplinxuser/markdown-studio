// Generate toolbar PNGs from Apple's SF Symbols.
// Run on macOS:  osascript -l JavaScript assets/generate-icons.js
ObjC.import('AppKit');

var output = ObjC.unwrap($.NSProcessInfo.processInfo.environment.objectForKey('MD_ICON_DIR')) ||
             (ObjC.unwrap($.NSFileManager.defaultManager.currentDirectoryPath) + '/assets/toolbar');

var symbols = {
  new: 'square.and.pencil',
  open: 'folder',
  save: 'square.and.arrow.down',
  undo: 'arrow.uturn.backward',
  redo: 'arrow.uturn.forward',
  bold: 'bold',
  italic: 'italic',
  strike: 'strikethrough',
  code: 'chevron.left.forwardslash.chevron.right',
  ul: 'list.bullet',
  ol: 'list.number',
  task: 'checklist',
  quote: 'text.quote',
  link: 'link',
  image: 'photo',
  table: 'tablecells',
  codeblock: 'curlybraces.square',
  hr: 'minus',
  preview: 'sidebar.right',
  plus: 'plus'
};

$.NSFileManager.defaultManager.createDirectoryAtPathWithIntermediateDirectoriesAttributesError(
  output, true, $(), $()
);

var failures = [];
Object.keys(symbols).forEach(function (key) {
  var name = symbols[key];
  var img = $.NSImage.imageWithSystemSymbolNameAccessibilityDescription(name, $());
  if (!img) {
    failures.push(key + ' (' + name + ')');
    return;
  }
  var cfg = $.NSImageSymbolConfiguration.configurationWithPointSizeWeightScale(
    18, $.NSFontWeightRegular, 3
  );
  var configured = img.imageWithSymbolConfiguration(cfg);
  var canvas = $.NSImage.alloc.initWithSize($.NSMakeSize(64, 64));
  canvas.lockFocus;
  configured.drawInRectFromRectOperationFraction(
    $.NSMakeRect(8, 8, 48, 48), $.NSZeroRect,
    $.NSCompositingOperationSourceOver, 1.0
  );
  canvas.unlockFocus;
  var rep = $.NSBitmapImageRep.imageRepWithData(canvas.TIFFRepresentation);
  var png = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $());
  png.writeToFileAtomically(output + '/' + key + '.png', true);
});

if (failures.length) {
  console.log('Missing symbols: ' + failures.join(', '));
} else {
  console.log('Generated ' + Object.keys(symbols).length + ' toolbar icons in ' + output);
}
