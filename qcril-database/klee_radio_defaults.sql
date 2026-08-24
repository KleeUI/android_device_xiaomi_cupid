-- Copyright (C) 2026 The KleeUI Project
-- SPDX-License-Identifier: Apache-2.0

-- Keep modern qcril behavior on top of the stock Cupid migration set without
-- replacing any carrier or emergency-number data supplied by the device.
UPDATE qcril_properties_table
SET def_val = 'true'
WHERE property = 'persist.vendor.radio.unicode_op_names';

UPDATE qcril_properties_table
SET def_val = 'false'
WHERE property = 'persist.vendor.radio.redir_party_num';

UPDATE qcril_properties_table
SET def_val = '0'
WHERE property = 'persist.vendor.radio.poweron_opt';
