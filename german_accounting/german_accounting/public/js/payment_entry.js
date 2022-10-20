frappe.ui.form.on('Payment Entry', {
	refresh: function (frm) {
		if(frm.doc.docstatus > 0) {
			frm.add_custom_button(__('Storno'), function() {
				console.log("pushed the button");
				frappe.call({
					method: "german_accounting.german_accounting.doctype.custom.payment_entry.create_reverse_entry",
					args: {
						doc: frm.doc
					},
					callback: function (r){
						console.log("called back.");
					}
				})
			});
		}
	}
})