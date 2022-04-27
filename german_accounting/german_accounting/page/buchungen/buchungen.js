frappe.pages['buchungen'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Buchungen',
		single_column: true
	});
	wrapper.test = new erpnext.Buchung(wrapper);
}


frappe.pages['buchungen'].refresh = function(wrapper){
	cur_page.page.page.set_primary_action("Buchen", function () {

    });
    //clear page after "submit" the form
    $('.primary-action:contains("Buchen")').click(function() {
        if(acc.account_soll.get_input_value() && acc.account_haben.get_input_value()){
            frappe.call({
                method: "german_accounting.german_accounting.page.buchungen.buchungen.generate_journal_entries",
                args: {
                    user: frappe.session.user_fullname,
                    acc_soll: acc.account_soll.get_input_value(),
                    voucher_id: acc.voucher_id.get_input_value(),
                    voucher_date: acc.voucher_date.get_input_value(),
                    acc_haben: acc.account_haben.get_input_value(),
                    value: acc.voucher_value.get_input_value(),
                    tax_kind: tax.tax_kind.get_input_value(),
                    tax_code: tax.tax_code.get_input_value(),
                    country_code: tax.country_code.get_input_value(),
                    tax_value: tax.tax_value.get_input_value(),
                    posting_text: tax.posting_text_1.get_input_value(),
                    fiscal_year: acc.fiscal_year.get_input_value(),
                    voucher_netto_value: acc.voucher_netto_value.get_input_value(),
                    booking_type: acc.booking_type.get_input_value(),
                    is_opening: acc.is_opening.get_input_value(),
                    cost_center: acc.cost_center.get_input_value(),
                    accounting_dimension: acc.accounting_dimension.get_input_value(),
                    project: acc.project.get_input_value(),
                    due_date: acc.due_date.get_input_value(),
                    service_contract: acc.service_contract.get_input_value(),
                    rental_service_contract: acc.rental_service_contract.get_input_value(),
                    maintenance_contract: acc.maintenance_contract.get_input_value(),
                    maintenance_contract_various: acc.maintenance_contract_various.get_input_value(),
                    cloud_and_hosting_contract: acc.cloud_and_hosting_contract.get_input_value(),
                },
                callback: function(r) {
                    var res = r.message;
                    if (res.generated == 1) {
                        frappe.ui.toolbar.clear_cache();
                    }
                }
            })
        } else {
            alert("Fehlende Felder")
        }
    });

    if (wrapper) {
        wrapper.make_buchung();
    }
}

erpnext.Buchung = class Buchung {
	constructor(wrapper) {
        this.wrapper = $(wrapper).find('.layout-main-section');
        this.page = wrapper.page;

        /*const assets = [
            'assets/erpnext/js/pos/clusterize.js',
        ];

        frappe.require(assets, () => {
            this.make();
        });*/
        this.make();

    }

    make() {
        return frappe.run_serially([
            () => frappe.dom.freeze(),
            () => {
                this.prepare_dom();
                this.set_online_status();
            },
            () => this.make_buchung(),
            () => this.make_tax(),
            () => frappe.dom.unfreeze(),
        ]);
    }

	prepare_dom() {
        this.wrapper.append(`
            <div class="pos">
                <section class="account-container">
                </section>
                <section class="tax-container">
                </section>
            </div>
        `);
    }

    set_online_status() {
        this.connection_status = false;
        this.page.set_indicator(__("Offline"), "grey");
        frappe.call({
            method: "frappe.handler.ping",
            callback: r => {
                if (r.message) {
                    this.connection_status = true;
                    this.page.set_indicator(__("Online"), "green");
                }
            }
        });
    }

    make_buchung() {
        this.acc = new Account({
            frm: this.frm,
            wrapper: this.wrapper.find('.account-container'),
        });


    }

    make_tax() {
        this.tax = new Tax({
            frm: this.frm,
            wrapper: this.wrapper.find('.tax-container'),
        });
    }


}

var acc;
class Account {
	constructor({frm, wrapper}) {
        this.frm = frm;
        this.wrapper = wrapper;
        this.make();
        acc = this;
    }


    make() {
        this.make_dom();
        this.make_input_fields();
    }

    make_dom() {
        this.wrapper.append(`
            <div class="account_wrapper">
                <div class="booking_type"></div>
                <div class="is_opening"></div>
                <br>
                <div class="account_soll"></div>
                <div class="voucher_id"></div>
                <div class="voucher_date"></div>
                <div class="due_date"></div>
                <div class="soll_total"></div>
                <div class="soll_s_h"></div>
                <div class="account_haben"></div>
                <div class="voucher_value"></div>
                <div class="voucher_netto_value"></div>
                <div class="haben_total"></div>
                <div class="fiscal_year"></div>
                <div class="cost_center"></div>
                <div class="accounting_dimension"></div>
                <div class="project"></div>
                <br>
                <div class="service_contract"></div>
                <div class="rental_service_contract"></div>
                <div class="maintenance_contract"></div>
                <div class="maintenance_contract_various"></div>
                <div class="cloud_and_hosting_contract"></div>
            </div>
        `);
    }

    make_input_fields() {

	    this.fiscal_year = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: 'Buchungsjahr',
                fieldname: 'fiscal_year',
                options: 'Fiscal Year',
            },
            parent: this.wrapper.find('.fiscal_year'),
            render_input: true
        });

        this.soll_total = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Currency',
                label: 'Soll Total',
                fieldname: 'soll_total',
                read_only: 1,
            },
            parent: this.wrapper.find('.soll_total'),
            render_input: true
        });

        this.soll_total = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Currency',
                label: 'Haben Total',
                fieldname: 'haben_total',
                read_only: 1,
            },
            parent: this.wrapper.find('.haben_total'),
            render_input: true
        });

        this.account_soll = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: 'Sollkonto',
                fieldname: 'account_soll',
                options: 'Account',
                change: function () {
                    frappe.call({
                        method: "german_accounting.german_accounting.page.buchungen.buchungen.calc_account_total_amount",
                        args: {
                            account: acc.account_soll.get_input_value(),
                            fiscal_year: acc.fiscal_year.get_input_value()
                        },
                        callback: function(r) {
                            var res = r.message;
                            $("div[data-fieldname='soll_total'] .control-value").text(res.value);
                        }
                    });
                }
            },
            parent: this.wrapper.find('.account_soll'),
            render_input: true
        });

        this.booking_type = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Select',
                label: 'Buchungstyp',
                fieldname: 'booking_type',
                options: ['Buchungssatz','Ausgangsrechnung','Eingangsrechnung'],
                default: 'Buchungssatz',
            },
            parent: this.wrapper.find('.booking_type'),
            render_input: true
        });

        this.is_opening = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Check',
                label: 'Ist EB-Wert',
                fieldname: 'is_opening',
            },
            parent: this.wrapper.find('.is_opening'),
            render_input: true
        });

        this.account_haben = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: 'Habenkonto',
                fieldname: 'account_haben',
                options: 'Account',
                change: function () {
                    frappe.call({
                        method: "german_accounting.german_accounting.page.buchungen.buchungen.calc_account_total_amount",
                        args: {
                            account: acc.account_haben.get_input_value(),
                            fiscal_year: acc.fiscal_year.get_input_value()
                        },
                        callback: function(r) {
                            var res = r.message;
                            $("div[data-fieldname='haben_total'] .control-value").text(res.value);
                        }
                    });
                }
            },
            parent: this.wrapper.find('.account_haben'),
            render_input: true
        });

        this.voucher_date = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Date',
                label: 'Belegdatum',
                fieldname: 'voucher_date',
            },
            parent: this.wrapper.find('.voucher_date'),
            render_input: true
        });

        this.due_date = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Date',
                label: 'Fälligkeitsdatum',
                fieldname: 'due_date',
            },
            parent: this.wrapper.find('.due_date'),
            render_input: true
        });

        this.voucher_id = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Data',
                label: 'Belegnummer',
                fieldname: 'voucher_id',
            },
            parent: this.wrapper.find('.voucher_id'),
            render_input: true
        });

        this.voucher_netto_value = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Currency',
                label: 'Nettobetrag',
                fieldname: 'voucher_netto_value',

            },
            parent: this.wrapper.find('.voucher_netto_value'),
            render_input: true
        });
        //alert( "Handler for .change() called." );
        this.voucher_value = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Currency',
                label: 'Betrag',
                fieldname: 'voucher_value',
                change: function () {
                    frappe.call({
                        method: "german_accounting.german_accounting.page.buchungen.buchungen.change_event_value",
                        args: {
                            value: acc.voucher_value.get_input_value(),
                            tax_kind: tax.tax_kind.get_input_value(),
                            tax_code: tax.tax_code.get_input_value(),
                        },
                        callback: function(r) {
                            var res = r.message;
                            $("input[data-fieldname='tax_value']").val(res['tax_value']);
                            $("input[data-fieldname='voucher_netto_value']").val(res['debit_value']);
                        }
                    });
                }
            },
            parent: this.wrapper.find('.voucher_value'),
            render_input: true
        });

        this.cost_center = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: 'Kostenstelle',
                fieldname: 'cost_center',
                options: 'Cost Center',
            },
            parent: this.wrapper.find('.cost_center'),
            render_input: true
        });

        this.accounting_dimension = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: 'Kostenträger',
                fieldname: 'accounting_dimension',
                options: 'Kostentraeger',
            },
            parent: this.wrapper.find('.accounting_dimension'),
            render_input: true
        });

        this.project = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: __('Project'),
                field_name: 'project',
                options: 'Project',
            },
            parent: this.wrapper.find('.project'),
            render_input: true
        });

        this.service_contract = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: "Service Contract",
                field_name: "service_contract",
                options: "Service Contract",
            },
            parent: this.wrapper.find('.service_contract'),
            render_input: true
        })

        this.rental_service_contract = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: 'Mietvertrage',
                field_name: 'rental_service_contract',
                options: 'Rental Server Contract',
            },
            parent: this.wrapper.find('.rental_service_contract'),
            render_input: true
        });
        this.maintenance_contract = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: __('Wartungsvertrag'),
                field_name: 'maintenance_contract',
                options: 'Maintenance Contract',
            },
            parent: this.wrapper.find('.maintenance_contract'),
            render_input: true
        });
        this.maintenance_contract_various = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: __('Wartungsvertrag Divers'),
                field_name: 'maintenance_contract_various',
                options: 'Maintenance Contract Various',
            },
            parent: this.wrapper.find('.maintenance_contract_various'),
            render_input: true
        });
        this.cloud_and_hosting_contract = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: __('Cloud und Hostingvertrag'),
                field_name: 'cloud_and_hosting_contract',
                options: 'Cloud And Hosting Contract',
            },
            parent: this.wrapper.find('.cloud_and_hosting_contract'),
            render_input: true
        });
    }
}

var tax;
class Tax {

	constructor({frm, wrapper}) {
        this.frm = frm;
        this.wrapper = wrapper;
        this.make();
        tax = this;
    }

    make() {
        this.make_dom();
        this.make_input_fields();

    }

    make_dom() {
        this.wrapper.append(`
            <div class="tax_wrapper">
                <div class="tax_kind">
                </div>
                <div class="tax_code">
                </div>
                <div class="country_code">
                </div>
                <div class="tax_value">
                </div>
                <div class="posting_text_1">
                </div>
            </div>
        `);
    }

    make_input_fields() {

        this.tax_kind = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Select',
                label: 'Steuerart',
                fieldname: 'tax_kind',
                options: ['0','VS','US'],
                change: function () {
                    if (tax.tax_kind.get_input_value() == "0"){
                      $("input[data-fieldname='tax_code']").val("");
                      $("input[data-fieldname='tax_value']").val("0");
                      $("input[data-fieldname='voucher_netto_value']").val(acc.voucher_value.get_input_value());
                    } else {
                        frappe.call({
                            method: "german_accounting.german_accounting.page.buchungen.buchungen.change_event_value",
                            args: {
                                value: acc.voucher_value.get_input_value(),
                                tax_kind: tax.tax_kind.get_input_value(),
                                tax_code: tax.tax_code.get_input_value(),
                            },
                            callback: function (r) {
                                var res = r.message;
                                $("input[data-fieldname='tax_value']").val(res['tax_value']);
                                $("input[data-fieldname='voucher_netto_value']").val(res['debit_value']);
                            }
                        });
                    }
                }
            },
            parent: this.wrapper.find('.tax_kind'),
            render_input: true
        });

        this.tax_code = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Link',
                label: 'Steuercode',
                fieldname: 'tax_code',
                options: 'Steuercodes',
                change: function () {
                    if (tax.tax_kind.get_input_value() == "0"){
                      $("input[data-fieldname='tax_code']").val("");
                      $("input[data-fieldname='tax_value']").val("0");
                      $("input[data-fieldname='voucher_netto_value']").val(acc.voucher_value.get_input_value());
                    } else {
                        frappe.call({
                            method: "german_accounting.german_accounting.page.buchungen.buchungen.change_event_value",
                            args: {
                                value: acc.voucher_value.get_input_value(),
                                tax_kind: tax.tax_kind.get_input_value(),
                                tax_code: tax.tax_code.get_input_value(),
                            },
                            callback: function (r) {
                                var res = r.message;
                                $("input[data-fieldname='tax_value']").val(res['tax_value']);
                                $("input[data-fieldname='voucher_netto_value']").val(res['debit_value']);
                            }
                        });
                    }
                }
            },
            parent: this.wrapper.find('.tax_code'),
            render_input: true
        });

        this.country_code = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Data',
                label: 'Ländercode',
                fieldname: 'country_code',
            },
            parent: this.wrapper.find('.country_code'),
            render_input: true
        });

        this.tax_value = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Currency',
                label: 'Steuer',
                fieldname: 'tax_value',
                read_only: 0,
            },
            parent: this.wrapper.find('.tax_value'),
            render_input: true
        });

        this.posting_text_1 = frappe.ui.form.make_control({
            df: {
                fieldtype: 'Data',
                label: 'Buchungstext',
            },
            parent: this.wrapper.find('.posting_text_1'),
            render_input: true
        });
    }
}
