mergeInto(LibraryManager.library, {
  VerificationNavigateur: function(ptr) { window.paintballVerification=JSON.parse(UTF8ToString(ptr)); },
  EtatNavigateur: function(ptr) { window.paintballState=JSON.parse(UTF8ToString(ptr)); }
});
