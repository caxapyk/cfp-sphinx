import argparse
import mariadb
import os
import textwrap
import sys
import time

pj = os.path.join


class CfpSphinx(object):
    """Pull data from CFP database and generate corresponding
    reStructuredText files into a Sphinx source path using templates.
    """

    def __init__(
            self, db_user, db_user_passwd, db_host, db_port, db_database):
        super(CfpSphinx, self).__init__()

        # Connect to MariaDB Platform
        try:
            conn = mariadb.connect(
                user=db_user,
                password=db_user_passwd,
                host=db_host,
                port=db_port,
                database=db_database
            )

        except mariadb.Error as e:
            print(f"Error connecting to MariaDB Platform: {e}")
            sys.exit(1)

        self.cur = conn.cursor()

        self.root_dir = os.path.join(
            os.path.abspath(os.getcwd()), 'nsa', 'cfp')

        # cfp/gubernia/index.rst
        # cfp/gubernia/<:id>/uezd/index.rst
        # cfp/gubernia/<:id>/uezd/<:id>/locality/index.rst
        # cfp/gubernia/<:id>/uezd/<:id>/locality/<:id>/church/index.rst
        # cfp/gubernia/<:id>/uezd/<:id>/locality/<:id>/church/<:id>/index.rst
        self.tree_templ = textwrap.dedent("""
        .. Tree RST template
        .. Autogenerated by cfp-sphinx.py

        {title}

        .. toctree::
           :maxdepth: 2

        {members}
        """)

        self.__current_gub = ''

    def make_dirs(self, path):
        """ Creates directories using path"""
        try:
            os.makedirs(os.path.join(self.root_dir, path), exist_ok=True)
        except OSError as e:
            print(f"Could not create directory: {e}")
            sys.exit(1)

    def cd(self, path):
        """ Change current directory"""
        try:
            os.chdir(os.path.join(self.root_dir, path))
        except OSError as e:
            print(f"Could not change directory: {e}")
            sys.exit(1)

    def file_write(self, fn, rst):
        """Writes RST content to file, creates one if not exists"""
        file = open(os.path.join(self.root_dir, fn), 'w+')
        file.write(rst)
        file.close()

    def format3(self, name):
        """Prepend 3 wite spaces."""
        return '   %s' % name

    def format_header(self, name):
        """Underline heder name"""
        return '%s\n' % name + ('=' * len(name))

    def __gen(self):
        current_dir = self.root_dir
        self.make_dirs(current_dir)

        self.cur.execute("SELECT id, name FROM cfp_gubernia")
        gubernias = self.cur.fetchall()

        for (g_id, g_name) in gubernias:
            print(f"{g_id}: {g_name}")

            g_dir = pj(current_dir, 'gubernia', str(g_id))
            self.make_dirs(g_dir)

            self.cur.execute(
                "SELECT id, name FROM cfp_uezd WHERE gub_id=?", (g_id,))
            uezds = self.cur.fetchall()

            for (u_id, u_name) in uezds:
                # print(f"   {u_id}: {u_name}")
                u_dir = pj(g_dir, 'uezd', str(u_id))
                self.make_dirs(u_dir)

                self.cur.execute(
                    "SELECT id, name FROM cfp_locality WHERE uezd_id=?", (u_id,))
                localities = self.cur.fetchall()

                for (l_id, l_name) in localities:
                    # print(f"      {l_id}: {l_name}")
                    l_dir = pj(u_dir, 'locality', str(l_id))
                    self.make_dirs(l_dir)

                    self.cur.execute(
                        "SELECT id, name FROM cfp_church WHERE locality_id=?", (l_id,))
                    churches = self.cur.fetchall()

                    for (ch_id, ch_name) in churches:
                        # print(f"         {ch_id}: {ch_name}")
                        ch_dir = pj(l_dir, 'church', str(ch_id))
                        self.make_dirs(ch_dir)

    def __gen_tree_index(self, path, content):
        """Creates RST index file using template"""
        self.file_write(pj(path, 'index.rst'), content)

    def __gen_gubernias(self, root_dir):
        self.cur.execute("SELECT id, name FROM cfp_gubernia")
        gubernias = self.cur.fetchall()

        _g_list = ''

        for (g_id, g_name) in gubernias:
            self.__current_gub = g_name
            print("%s\tloading..." % self.__current_gub, end=' ', flush=True)

            _g_list += self.format3(g_id) + '/index' + '\n'

            child_dir = pj(root_dir, 'gubernia', str(g_id))
            self.make_dirs(child_dir)

            self.__gen_uezds(g_id, g_name, child_dir)

            print("\r%s\tDone!     " %
                  self.__current_gub, end='\n', flush=True)

        rst = self.tree_templ.format(
            title=None, members=_g_list)
        self.__gen_tree_index('gubernia', rst)

    def __gen_uezds(self, g_id, g_name, pdir):
        self.cur.execute(
            "SELECT id, name FROM cfp_uezd WHERE gub_id=?", (g_id,))
        uezds = self.cur.fetchall()

        _u_list = ''

        for (u_id, u_name) in uezds:
            _u_list += self.format3(f'uezd/{u_id}/index\n')

            child_dir = pj(pdir, 'uezd', str(u_id))
            self.make_dirs(child_dir)

            self.__gen_localities(u_id, u_name, child_dir)

        rst = self.tree_templ.format(
            title=g_name, members=_u_list)
        self.__gen_tree_index(pdir, rst)

    def __gen_localities(self, u_id, u_name, pdir):
        self.cur.execute(
            "SELECT id, name FROM cfp_locality WHERE uezd_id=?", (u_id,))
        localities = self.cur.fetchall()

        _l_list = ''

        for (l_id, l_name) in localities:
            _l_list += self.format3(f'uezd/{l_id}/index\n')

            child_dir = pj(pdir, 'locality', str(l_id))
            self.make_dirs(child_dir)

            self.__gen_churches(l_id, l_name, child_dir)

        rst = self.tree_templ.format(
            title=u_name, members=_l_list)
        self.__gen_tree_index(pdir, rst)

    def __gen_churches(self, l_id, l_name, pdir):
        self.cur.execute(
            "SELECT id, name FROM cfp_church WHERE locality_id=?", (l_id,))
        churches = self.cur.fetchall()

        _ch_list = ''

        for (ch_id, ch_name) in churches:
            _ch_list += self.format3(f'uezd/{ch_id}/index\n')

            child_dir = pj(pdir, 'church', str(ch_id))
            self.make_dirs(child_dir)

        rst = self.tree_templ.format(
            title=l_name, members=_ch_list)
        self.__gen_tree_index(pdir, rst)

    def generate(self):
        self.make_dirs(self.root_dir)
        self.__gen_gubernias(self.root_dir)

    # def __gen_gubernias(self):
    #    gub_cur = self.conn.cursor()
    #   gub_cur.execute("SELECT * FROM cfp_gubernia")
    #    _sub_list = ""
#
    #    for (id, name) in gub_cur:
    #        self.__data['gubernia']['list'].append((id, name))
    #        print(f"Gubernia ID: {id}, Gubernia Name: {name}")
#
    #        # create sub-folders, save list of paths for toctree
    #        _sub = os.path.join(self.__data['gubernia']['dir'], str(id))
    #        _sub_list += self.format3(id) + '/index' + '\n'
    #        self.make_dirs(_sub)

        # create index file
    #    self.file_write(
    #        os.path.join(self.__data['gubernia']['dir'], 'index.rst'),
    #        self.tree_templ.format(parent=None, members=_sub_list))

    # def __gen_uezds(self):
    #    uezd_cur = self.conn.cursor()
    #    for (parent_id, parent_name) in self.__data['gubernia']['list']:
        #       uezd_cur.execute(
    #            "SELECT * FROM cfp_uezd WHERE gub_id=?", (parent_id,))
    #        _sub_list = ""
#
        #       for (id, gub_id, name) in uezd_cur:
        #           self.__data['uezd']['list'].append((id, name))
    #            print(f"Uezd ID: {id}, Gubernia ID: {gub_id}, Uezd name: {name}")
#
        # create sub-folders, save list of paths for toctree
    #            parent_path = os.path.join(
        #               self.__data['gubernia']['dir'], str(gub_id))
    #            _sub = os.path.join(self.__data['uezd']['dir'], str(id))
        #           _sub_list += self.format3(_sub) + '/index' + '\n'
#
        #           self.make_dirs(os.path.join(parent_path, _sub))
#
    #        # create index file
    #        self.file_write(
    #            os.path.join(parent_path, 'index.rst'),
    #            self.tree_templ.format(
        #               parent=self.format_header(parent_name),
        #               members=_sub_list))


def main():
    parser = argparse.ArgumentParser(
        description='CfpSphinx RST autogen 2020 Sakharuk Alexander')

    parser.add_argument('--db', default='cfp',
                        action='store', help='Database name')
    parser.add_argument('--host', default='localhost',
                        action='store', help='Database hostname')
    parser.add_argument('--port', default=3306,
                        action='store', help='Database port')
    parser.add_argument('--password', default='',
                        action='store', help='Database password')
    parser.add_argument('--user', default='root',
                        action='store', help='Database username')

    args = parser.parse_args()

    cfpsphinx = CfpSphinx(args.user, args.password,
                          args.host, args.port, args.db)
    cfpsphinx.generate()


if __name__ == '__main__':
    main()
