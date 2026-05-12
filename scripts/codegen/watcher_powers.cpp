        // ********************* WATCHER POWERS *********************

        case CardId::DEVOTION: {
            player.buff<PS::DEVOTION>(up ? 3 : 2);
            break;
        }

        case CardId::NIRVANA: {
            player.buff<PS::NIRVANA>(up ? 2 : 1);
            break;
        }

        case CardId::RUSHDOWN: {
            player.buff<PS::RUSHDOWN>(1);
            break;
        }

        case CardId::MENTAL_FORTRESS: {
            player.buff<PS::MENTAL_FORTRESS>(up ? 4 : 3);
            break;
        }

        case CardId::ESTABLISHMENT: {
            player.buff<PS::ESTABLISHMENT>(1);
            break;
        }

        case CardId::FORESIGHT: {
            player.buff<PS::FORESIGHT>(up ? 4 : 3);
            break;
        }

        case CardId::BATTLE_HYMN: {
            player.buff<PS::BATTLE_HYMN>(up ? 2 : 1);
            break;
        }

        case CardId::FASTING: {
            player.buff<PS::FASTING>(up ? 4 : 3);
            break;
        }

        case CardId::LIKE_WATER: {
            player.buff<PS::LIKE_WATER>(up ? 7 : 5);
            break;
        }

        case CardId::MASTER_REALITY: {
            player.buff<PS::MASTER_REALITY>(1);
            break;
        }

        case CardId::DEVA_FORM: {
            player.buff<PS::DEVA>(1);
            break;
        }

        case CardId::STUDY: {
            player.buff<PS::STUDY>(up ? 2 : 1);
            break;
        }

        case CardId::BUFFER: {
            player.buff<PS::BUFFER>(up ? 2 : 1);
            break;
        }

        case CardId::OMEGA: {
            player.buff<PS::OMEGA>(1);
            break;
        }
