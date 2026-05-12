        // ********************* SILENT POWERS *********************

        case CardId::ACCURACY:
            addToBot( Actions::BuffPlayer<PS::ACCURACY>(up ? 6 : 4) );
            break;

        case CardId::AFTER_IMAGE:
            addToBot( Actions::BuffPlayer<PS::AFTER_IMAGE>(1) );
            break;

        case CardId::A_THOUSAND_CUTS:
            addToBot( Actions::BuffPlayer<PS::THOUSAND_CUTS>(up ? 2 : 1) );
            break;

        case CardId::CALTROPS:
            addToBot( Actions::BuffPlayer<PS::THORNS>(up ? 5 : 3) );
            break;

        case CardId::ENVENOM:
            addToBot( Actions::BuffPlayer<PS::ENVENOM>(1) );
            break;

        case CardId::FOOTWORK:
            addToBot( Actions::BuffPlayer<PS::DEXTERITY>(up ? 3 : 2) );
            break;

        case CardId::INFINITE_BLADES:
            addToBot( Actions::BuffPlayer<PS::INFINITE_BLADES>(1) );
            break;

        case CardId::NOXIOUS_FUMES:
            addToBot( Actions::BuffPlayer<PS::NOXIOUS_FUMES>(up ? 3 : 2) );
            break;

        case CardId::TOOLS_OF_THE_TRADE:
            addToBot( Actions::BuffPlayer<PS::TOOLS_OF_THE_TRADE>(1) );
            break;

        case CardId::WELL_LAID_PLANS:
            addToBot( Actions::BuffPlayer<PS::RETAIN_CARDS>(up ? 2 : 1) );
            break;

        // CardId::WRAITH_FORM is defined natively in STS lightspeed
