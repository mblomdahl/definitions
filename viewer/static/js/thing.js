$(function () {

  $('.link-item').each(function() {
    $(this).prepend('<div class="chip-expanded">'+ $(this).html() +'</div>');
    var chip = $(this).find('.chip-expanded');
  });

  $('.link-item').hover(function() {
    var chip = $(this).find('.chip-expanded');
    var parent = $(this);
    
    // Calculate if we're outside viewport
    var diff = (parent.offset().left + chip.width()) - $(window).width()
    var xMove = 0;
    if(diff > 0) {
      xMove += diff + 20;
    }
    
    chip.addClass('to-be-active');
    setTimeout(function() {
      if(chip.hasClass('to-be-active'))
        chip.addClass('active').removeClass('to-be-active');
        chip.css('margin-left', (-xMove));
    }, 500);
  }, function() {
    var chip = $(this).find('.chip-expanded');
    chip.removeClass('active').removeClass('to-be-active');
  });

  $(document).ready(function () {
  });

});
