// First-admin bootstrap for the SCL leosac-server host.
//
// The websock-api module gates every message behind an authenticated
// APISession (only get_leosac_version / create_auth_token /
// authenticate_with_token pass pre-auth), so the first admin cannot be created
// over the WebSocket API. This helper persists it straight through the same ODB
// layer the daemon uses (User::password() does the libscrypt hashing:
// N=16384, r=8, p=1, dklen=64, 16-byte random salt — same code path as the
// server, no hash-format guessing).
//
// Compiled at image-build time against the built tree (see Dockerfile). Run
// AFTER leosac has started once (it creates the schema on startup):
//   leosac-create-admin [username] [password]
// Idempotent: updates password + rank if the user already exists.

#include <iostream>
#include <memory>

#include <odb/database.hxx>
#include <odb/transaction.hxx>
#include <odb/pgsql/database.hxx>

#include "core/auth/User.hpp"
#include "core/auth/User_odb.h"

int main(int argc, char **argv)
{
    const std::string username = (argc > 1) ? argv[1] : "admin";
    const std::string password = (argc > 2) ? argv[2] : "admin";

    try
    {
        // Same connection parameters as kernel.xml.
        auto db = std::make_shared<odb::pgsql::database>(
            "leosac", "leosac123", "leosac", "127.0.0.1", 5432);

        odb::transaction t(db->begin());

        auto existing = db->query_one<Leosac::Auth::User>(
            odb::query<Leosac::Auth::User>::username == username);
        if (existing)
        {
            existing->password(password);
            existing->rank(Leosac::Auth::UserRank::ADMIN);
            db->update(existing);
            t.commit();
            std::cout << "leosac-create-admin: updated existing user '" << username
                      << "' (password + ADMIN rank)" << std::endl;
        }
        else
        {
            auto user       = std::make_shared<Leosac::Auth::User>(username);
            user->password(password);
            user->rank(Leosac::Auth::UserRank::ADMIN);
            db->persist(user);
            t.commit();
            std::cout << "leosac-create-admin: created admin user '" << username
                      << "'" << std::endl;
        }
        return 0;
    }
    catch (const std::exception &e)
    {
        std::cerr << "leosac-create-admin failed: " << e.what() << std::endl;
        return 1;
    }
}
