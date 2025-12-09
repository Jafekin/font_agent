var Dialog = {
    warn : function(){
        Dialog.__smallBox.call(this,"warn",arguments);
    },
    success : function(){
        Dialog.__smallBox.call(this,"success",arguments);
    },
    error : function(){
        Dialog.__smallBox.call(this,"error",arguments)
    },
    info : function(){
        Dialog.__smallBox.call(this, "info", arguments);
    },
    __smallBox : function(level,args){
        var content="",icon,bg;
        if("warn"==level){
            icon="glyphicon-warning-sign";
            bg="alert-warning";
        }
        if("success"==level){
            bg="alert-success";
            icon="glyphicon-ok-sign";
        }
        if("info"==level) {
            bg="alert-info";
            icon="glyphicon-info-sign";
        }
        if("error"==level) {
            icon="glyphicon-remove-sign";
            bg="alert-danger";
        }
        if(args.length == 1){content=args[0]}
        else {content = args[1];}
        var obj = $('<div class="dialog-alert"><div class="alert ' + bg + '" role="alert"><i class="alert-icon glyphicon ' + icon + '"></i><span class="alert-msg"></span></div></div>')
            .appendTo($(document.body));
        $(".alert-msg", obj).text(content);
        obj.show().animateCss("fadeInDown", function(){
            var closeAlert = function(){obj.animateCss("fadeOutUp", function(){obj.remove()})}
            obj.click(closeAlert);
            setTimeout(closeAlert, 3000);
        });
    }
}