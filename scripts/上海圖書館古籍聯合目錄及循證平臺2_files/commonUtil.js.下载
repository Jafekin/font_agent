
/**
 * 字符串格式化，接受传递参数
 */
String.format = function() {
    if( arguments.length == 0 )
        return null;
    var str = arguments[0]; 
    for(var i=1;i<arguments.length;i++) {
        var re = new RegExp('\\{' + (i-1) + '\\}','gm');
        str = str.replace(re, arguments[i]);
    }
    return str;
}


String.prototype.endWith=function(s){
	  if(s==null||s==""||this.length==0||s.length>this.length)
	     return false;
	  if(this.substring(this.length-s.length)==s)
	     return true;
	  else
	     return false;
	  return true;
	 }

	 String.prototype.startWith=function(s){
	  if(s==null||s==""||this.length==0||s.length>this.length)
	   return false;
	  if(this.substr(0,s.length)==s)
	     return true;
	  else
	     return false;
	  return true;
	 }
	 
	 

		
		/**
		 * form转换为json
		 */ 
		$.fn.toJson = function(){
		    var obj = {};
		    var count = 0;
		    $.each( this.serializeArray(), function(i,o){
		        var n = o.name, v = o.value;
		        count++;
		        obj[n] = obj[n] === undefined ? v
		        : $.isArray( obj[n] ) ? obj[n].concat( v )
		        : [ obj[n], v ];
		    });
		    // obj.nameCounts = count + "";//表单name个数
		    return obj;
		};

		/**
		 * 合并json
		 */
		function mergeJson(src, dest) {  
		    var i;  
		    for(i in src) {  
		        dest[i]=src[i];  
		    }  
		    return dest;  
		}  
		
		
		/**
		 * 取得光标在单行文本框位置
		 */
		function getPositionForInput(ctrl) {
			var CaretPos = 0;
			if (document.selection) { // IE Support
				ctrl.focus();
				var Sel = document.selection.createRange();
				Sel.moveStart('character', -ctrl.value.length);
				CaretPos = Sel.text.length;
			} else if (ctrl.selectionStart || ctrl.selectionStart == '0') {// Firefox
				CaretPos = ctrl.selectionStart;
			}else{
			}
			return (CaretPos);
		}
		
		/**
		 * 取得光标在多行文本框位置
		 */ 
		function getPositionForTextArea(ctrl) {
			var CaretPos = 0;
			if (document.selection) {// IE Support
				ctrl.focus();
				var Sel = document.selection.createRange();
				var Sel2 = Sel.duplicate();
				Sel2.moveToElementText(ctrl);
				var CaretPos = -1;
				while (Sel2.inRange(Sel)) {
					Sel2.moveStart('character');
					CaretPos++;
				}
			} else if (ctrl.selectionStart || ctrl.selectionStart == '0') {// Firefox
																			// support
				CaretPos = ctrl.selectionStart;
			}
			return (CaretPos);
		}

		/**
		 * 不足位前面加0
		 * @param str
		 * @param lenght 长度
		 * @returns
		 */
		function padLeftZero(str, lenght) {
			var str=str+'';
	        while (str.length < lenght){
	        	str='0' + str;
	        }
	        return str;
	    }
